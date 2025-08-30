"""
Flask web application that replicates the dynamic exam flow.  Question
sets are stored in external JSON files which are indexed at startup.
"""
from __future__ import annotations

import os
from datetime import timedelta
from typing import Dict, Any, List

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    current_app,
    send_from_directory,
)

from pathlib import Path

import data_loader


def create_app() -> Flask:
    """Create and configure the Flask application.

    This application serves both the dynamic exam flow and the static pages
    captured from the original site.  The static HTML, CSS, JS and image
    assets live in the same directory as this file and are made available
    via Flask's static file handling by specifying the app's static_folder
    and static_url_path.  Dynamic templates are used only for the actual
    exam questions and results; selection and pre-exam overview pages are
    served as static HTML.
    """
    # The root of the repository where the HTTrack mirror has been copied
    app_root = Path(__file__).parent
    # Expose every file under app_root at the root URL.  Dynamic routes
    # defined below will override static files with the same path.
    app = Flask(
        __name__,
        static_folder=str(app_root),
        static_url_path="",
    )
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
    app.permanent_session_lifetime = timedelta(hours=1)

    # Build initial index of available exam sets
    app.config["EXAM_INDEX"] = data_loader.build_index()

    # Refresh index on each request in debug mode
    @app.before_request
    def refresh_index() -> None:
        if app.debug:
            app.config["EXAM_INDEX"] = data_loader.build_index()

    MODE_LABELS = {
        "easy": "かんたん受験",
        "standard": "標準受験",
        "full": "本番受験",
    }
    CATEGORY_LABELS = {
        "language": "言語",
        "nonverbal": "非言語",
        "english": "英語",
    }

    @app.route("/")
    def home() -> str:
        # Redirect to the static select-mode page.  Because static files are served
        # from the app root (via static_url_path=""), url_for('static', filename=...)
        # will generate the correct URL to the HTML file.  This avoids rendering
        # unused Jinja templates for the mode selection screen.
        return redirect(url_for("static", filename="exam/select-mode.html"))

    @app.route("/exam/select-mode")
    def select_mode() -> str:
        """Redirect to the static select-mode page.

        The original site served the mode selection as a plain HTML file.  Since
        the HTTrack mirror has been copied into the application root, use
        Flask's static file serving to return that file directly.  This avoids
        relying on a Jinja template for the selection screens.
        """
        return redirect(url_for("static", filename="exam/select-mode.html"))

    @app.route("/exam/select-category/<mode>")
    def select_category(mode: str) -> str:
        """Redirect to the static category selection page for the given mode.

        For example, requesting /exam/select-category/easy will return
        the file exam/select-category/easy.html.  If the file does not
        exist, the dynamic fallback remains available via Flask's static
        error handling.
        """
        filename = f"exam/select-category/{mode}.html"
        return redirect(url_for("static", filename=filename))

    @app.route("/exam/pre-exam/<slug>")
    def pre_exam(slug: str) -> str:
        index = current_app.config["EXAM_INDEX"]
        meta = index.get(slug)
        if not meta:
            flash("選択された問題セットが存在しません。", "error")
            return redirect(url_for("select_mode"))
        try:
            data = data_loader.load_set(slug)
        except Exception:
            flash("問題データの読み込みに失敗しました。", "error")
            return redirect(url_for("select_mode"))
        info = {
            "title": data["title"],
            "description": data.get("description", ""),
            "mode": meta["mode"],
            "category": meta["category"],
            "question_set_id": meta["slug"],
            "num_questions": meta["num_questions"],
            "time_limit_minutes": meta["time_per_question_sec"] * meta["num_questions"] // 60,
        }
        return render_template("pre_exam.html", info=info)

    @app.post("/exam/start")
    def exam_start() -> Any:
        slug = request.form.get("question_set_id")
        index = current_app.config["EXAM_INDEX"]
        if not slug or slug not in index:
            flash("無効な問題セットです。", "error")
            return redirect(url_for("select_mode"))
        try:
            data = data_loader.load_set(slug)
        except Exception:
            flash("問題データの読み込みに失敗しました。", "error")
            return redirect(url_for("select_mode"))
        session.permanent = True
        session["question_set_id"] = slug
        session["current_index"] = 0
        session["answers"] = []
        session["time_per_question_sec"] = data["time_per_question_sec"]
        return redirect(url_for("exam_question"))

    @app.route("/exam/question")
    def exam_question() -> Any:
        slug = session.get("question_set_id")
        index = session.get("current_index", 0)
        if not slug:
            flash("受験が開始されていません。", "error")
            return redirect(url_for("select_mode"))
        try:
            data = data_loader.load_set(slug)
        except Exception:
            flash("問題データの読み込みに失敗しました。", "error")
            return redirect(url_for("select_mode"))
        questions = data["questions"]
        if index >= len(questions):
            return redirect(url_for("exam_result"))
        question = questions[index]
        time_limit = session.get("time_per_question_sec", data["time_per_question_sec"])
        subject_title = data["title"]
        return render_template(
            "exam.html",
            question=question,
            index=index,
            total=len(questions),
            time_limit=time_limit,
            subject_title=subject_title,
        )

    @app.post("/exam/answer")
    def exam_answer() -> Any:
        selected = request.form.get("option")
        slug = session.get("question_set_id")
        index = session.get("current_index", 0)
        if not slug:
            flash("セッションが無効です。", "error")
            return redirect(url_for("select_mode"))
        try:
            data_loader.load_set(slug)
        except Exception:
            flash("問題データの読み込みに失敗しました。", "error")
            return redirect(url_for("select_mode"))
        try:
            selected_index = int(selected) if selected is not None else None
        except (TypeError, ValueError):
            selected_index = None
        answers: List[int | None] = session.get("answers", [])
        if len(answers) <= index:
            answers.append(selected_index)
        else:
            answers[index] = selected_index
        session["answers"] = answers
        session["current_index"] = index + 1
        return redirect(url_for("exam_question"))

    @app.route("/exam/result")
    def exam_result() -> str:
        slug = session.get("question_set_id")
        answers = session.get("answers", [])
        if not slug:
            flash("結果を表示できません。", "error")
            return redirect(url_for("select_mode"))
        try:
            data = data_loader.load_set(slug)
        except Exception:
            flash("問題データの読み込みに失敗しました。", "error")
            return redirect(url_for("select_mode"))
        questions = data["questions"]
        score = 0
        for idx, q in enumerate(questions):
            if idx < len(answers) and answers[idx] is not None and answers[idx] == q["answer_index"]:
                score += 1
        session.pop("question_set_id", None)
        session.pop("current_index", None)
        session.pop("answers", None)
        session.pop("time_per_question_sec", None)
        return render_template("results.html", total=len(questions), score=score)

    @app.route("/api/status")
    def api_status() -> Any:
        return jsonify({"status": "ok"})

    @app.context_processor
    def inject_now() -> Dict[str, Any]:
        from datetime import datetime
        return {"current_year": datetime.now().year}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
