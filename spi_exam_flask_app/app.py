"""Flask web application serving static exam pages and dynamic routes."""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
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
    abort,
)

import data_loader

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = REPO_ROOT / "teraz"


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
    app.permanent_session_lifetime = timedelta(hours=1)

    # Build initial index of available exam sets
    app.config["EXAM_INDEX"] = data_loader.build_index()

    # Refresh index on each request in debug mode
    @app.before_request
    def refresh_index() -> None:
        if app.debug:
            app.config["EXAM_INDEX"] = data_loader.build_index()

    @app.route("/")
    def root() -> Any:
        return redirect(url_for("select_mode_html"))

    @app.route("/exam/select-mode")
    def select_mode_html() -> Any:
        return send_from_directory(STATIC_ROOT / "exam", "select-mode.html")

    @app.route("/exam/select-category/<mode>")
    def select_category_html(mode: str) -> Any:
        return send_from_directory(STATIC_ROOT / "exam" / "select-category", f"{mode}.html")

    @app.route("/exam/pre-exam/<path:filename>")
    def pre_exam_html(filename: str):
        if "/" in filename or ".." in filename:
            abort(400)
        return send_from_directory(STATIC_ROOT / "exam" / "pre-exam", filename)

    @app.route("/css/<path:filename>")
    def css_static(filename: str):
        return send_from_directory(STATIC_ROOT / "css", filename)

    @app.route("/js/<path:filename>")
    def js_static(filename: str):
        return send_from_directory(STATIC_ROOT / "js", filename)

    @app.route("/images/<path:filename>")
    def img_static(filename: str):
        return send_from_directory(STATIC_ROOT / "images", filename)

    @app.route("/build/<path:filename>")
    def build_static(filename: str):
        return send_from_directory(STATIC_ROOT / "build", filename)

    @app.get("/healthz")
    def healthz() -> str:
        return "ok"

    @app.post("/exam/start")
    def exam_start() -> Any:
        slug = request.form.get("question_set_id")
        index = current_app.config["EXAM_INDEX"]
        if not slug or slug not in index:
            flash("無効な問題セットです。", "error")
            return redirect(url_for("select_mode_html"))
        try:
            data = data_loader.load_set(slug)
        except Exception:
            flash("問題データの読み込みに失敗しました。", "error")
            return redirect(url_for("select_mode_html"))
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
            return redirect(url_for("select_mode_html"))
        try:
            data = data_loader.load_set(slug)
        except Exception:
            flash("問題データの読み込みに失敗しました。", "error")
            return redirect(url_for("select_mode_html"))
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
            return redirect(url_for("select_mode_html"))
        try:
            data_loader.load_set(slug)
        except Exception:
            flash("問題データの読み込みに失敗しました。", "error")
            return redirect(url_for("select_mode_html"))
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
            return redirect(url_for("select_mode_html"))
        try:
            data = data_loader.load_set(slug)
        except Exception:
            flash("問題データの読み込みに失敗しました。", "error")
            return redirect(url_for("select_mode_html"))
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
