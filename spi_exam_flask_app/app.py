"""
Flask web application that replicates the dynamic exam flow.

方針（完成版）:
- 先頭画面は HTTrack ミラーの `index.html` をそのまま表示する。
- モード選択 / カテゴリ選択 / プレ受験ページは **静的 HTML**（HTTrack ミラー）を返す。
  ※ プレ受験ページは既に `<form method="POST" action="/exam/start">` と
     `question_set_id` の hidden が入っている前提。
- 「受験スタート」以降（設問～結果）は **Flask の動的テンプレート**で表示する。
- 静的資産（HTML/CSS/JS/画像等）は本ファイルと同じディレクトリ配下から配信する。
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Dict, Any, List
from pathlib import Path

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
)

import data_loader


def create_app() -> Flask:
    """Create and configure the Flask application."""
    # 本ファイルが置かれているディレクトリを「静的ルート」にする
    # （この下に HTTrack ミラーの HTML/CSS/JS/画像が配置されている想定）
    app_root = Path(__file__).parent

    app = Flask(
        __name__,
        static_folder=str(app_root),  # 静的配信のルート
        static_url_path="",           # ルート（/）直下にマッピング
    )
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
    app.permanent_session_lifetime = timedelta(hours=1)

    # 起動時に問題セットのインデックスを構築
    app.config["EXAM_INDEX"] = data_loader.build_index()

    # Debug のときは毎リクエストでインデックスを再構築（ホットリロード想定）
    @app.before_request
    def _refresh_index() -> None:
        if app.debug:
            app.config["EXAM_INDEX"] = data_loader.build_index()

    # ──────────────────────────────────────────────────────────────
    # 静的ページ（HTTrack ミラー）: index / select-mode / select-category / pre-exam
    # ──────────────────────────────────────────────────────────────

    @app.route("/")
    def home() -> str:
        """最初に `index.html` を表示する。"""
        return redirect(url_for("static", filename="index.html"))

    @app.route("/exam/select-mode")
    def select_mode() -> str:
        """モード選択は静的 HTML を返す。"""
        return redirect(url_for("static", filename="exam/select-mode.html"))

    @app.route("/exam/select-category/<mode>")
    def select_category(mode: str) -> Any:
        """
        カテゴリ選択は静的 HTML を返す。
        `easy` のように拡張子なしで来たら `easy.html` にリダイレクト。
        すでに `easy.html` のように拡張子付きならそのまま静的配信。
        """
        filename = f"exam/select-category/{mode}"
        if not filename.endswith(".html"):
            return redirect(url_for("static", filename=filename + ".html"))
        # `.html` が付いている場合はそのまま返す
        return current_app.send_static_file(filename)

    # ※ 重要:
    # 以前存在した `/exam/pre-exam/<slug>` の **動的ルートは定義しない**。
    # プレ受験画面は HTTrack ミラーの静的 HTML（例: /exam/pre-exam/antonym_english_4q.html 等）を
    # そのまま返すため、Flask の動的ルートで横取りしない。静的配信に任せる。
    #
    # 具体的には:
    #   /exam/pre-exam/antonym_english_4q.html -> static file (HTTrack)
    #   /exam/pre-exam/easy_1000f6.html     -> static file (HTTrack)
    # これら静的ページの <form action="/exam/start"> が POST を投げる。

    # ──────────────────────────────────────────────────────────────
    # 受験開始以降（動的）
    # ──────────────────────────────────────────────────────────────

    @app.post("/exam/start")
    def exam_start() -> Any:
        """プレ受験ページからの POST を受け取り、セッションを初期化して設問へ。"""
        slug = request.form.get("question_set_id")
        index_map = current_app.config["EXAM_INDEX"]

        if not slug or slug not in index_map:
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
        """現在の設問を表示。時間切れや回答後は次の設問に遷移。"""
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
        """ラジオボタンの選択を受け取り、次の設問へ。"""
        selected = request.form.get("option")
        slug = session.get("question_set_id")
        index = session.get("current_index", 0)

        if not slug:
            flash("セッションが無効です。", "error")
            return redirect(url_for("select_mode"))

        # データの存在だけ確認（例外処理はユーザー向けメッセージで隠蔽）
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
        """スコアを計算して結果を表示。最後に受験関連のセッションをクリア。"""
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

        # 受験関連のセッションをクリア
        for k in ("question_set_id", "current_index", "answers", "time_per_question_sec"):
            session.pop(k, None)

        return render_template("results.html", total=len(questions), score=score)

    # ──────────────────────────────────────────────────────────────
    # ユーティリティ
    # ──────────────────────────────────────────────────────────────

    @app.route("/api/status")
    def api_status() -> Any:
        return jsonify({"status": "ok"})

    @app.context_processor
    def inject_now() -> Dict[str, Any]:
        from datetime import datetime

        return {"current_year": datetime.now().year}

    return app


if __name__ == "__main__":
    # ローカル実行用
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5050)), debug=True)
