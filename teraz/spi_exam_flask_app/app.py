"""
Flask web application that replicates the dynamic exam flow from the
spi.bakusoku‑shukatsu.jp site.  This app is not intended to be a
drop‑in replacement for the original service but rather a study aid
that demonstrates how one might implement a timed question set with
session state.  All questions and user interface elements are
original, and no proprietary assets from the original site are
included.  To run this application locally, install Flask (`pip
install Flask`) and run `python app.py`.  Then open
http://localhost:5000 in your browser.

This file defines the Flask application, routes and simple HTML
templates to serve the exam.  Session cookies are used to track
progress and answers.  A configurable dictionary defines question
sets.
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Dict, List, Any

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    # Secret key for signing session cookies.  In production use a
    # strong random value stored outside of source control.
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
    # Configure session lifetime (used for exam timing).  Here we set
    # session cookies to expire after 1 hour of inactivity.
    app.permanent_session_lifetime = timedelta(hours=1)

    # Define some example question sets.  Each set maps to a list of
    # dictionaries with question text, a list of options and the index
    # of the correct option.  Feel free to customize these or load
    # them from a JSON/YAML file.
    # Define the question sets used in the exam.  Each entry maps a
    # set identifier (e.g. "easy_language") to a list of question
    # dictionaries.  The dictionaries specify the question text
    # (HTML is allowed), a list of options and the index of the
    # correct option.  These sample questions are entirely original
    # and serve only as placeholders for your own content.
    QUESTION_SETS: Dict[str, List[Dict[str, Any]]] = {
        # Language questions for the easy exam.  Five sample
        # questions illustrate different option layouts (single
        # choice, paired choices etc.).
        "easy_language": [
            {
                "question": """
                最初に示された二語の関係を考えて、同じ関係のものを選んでください。<br><br>
                慈善 ： 寄付<br><br>
                ア. 太陽 ： 光<br>
                イ. 教育 ： 授業<br>
                ウ. 研究 ： 発表
                """,
                "options": [
                    "アだけ",
                    "イだけ",
                    "ウだけ",
                    "アとイ",
                    "アとウ",
                    "イとウ",
                ],
                # In this example we mark "アとウ" (index 4) as the
                # correct answer because both 太陽:光 and 研究:発表
                # represent a source‑result relationship, whereas 教育:授業
                # is more analogous to method and class.
                "answer": 4,
            },
            {
                "question": """
                下記の表現と、意味が合致するものを1つ選びなさい。<br><br>
                感謝の気持ちを言葉や行動で表すこと。
                """,
                "options": [
                    "口を閉ざす",
                    "手をつなぐ",
                    "感謝を示す",
                    "遠慮する",
                    "足を引きずる",
                ],
                "answer": 2,
            },
            {
                "question": """
                下線部の語が最も近い意味で使われているものを1つ選びなさい。<br><br>
                その件については、しっかり<u>まとめる</u>べきだ。<br><br>
                """,
                "options": [
                    "彼は自分の荷物をまとめた。",
                    "先生は彼の文章をまとめていた。",
                    "その選手は世界中で称賛されている。",
                    "社長は新しいプロジェクトをまとめた。",
                    "彼は部屋に誰かがいるのをまとめた。",
                ],
                # The correct answer is option 3 (index 3: 社長は新しいプロジェクトをまとめた)
                "answer": 3,
            },
            {
                "question": """
                AからEの文を[1]から[5]に入れて文の意味が通るようにしたとき、[4]に当てはまるものを選びなさい。<br><br>
                読書の習慣が広がる背景には[1][2][3][4][5]といった要因がある。
                """,
                "options": [
                    "A",
                    "B",
                    "C",
                    "D",
                    "E",
                ],
                # In this example we arbitrarily choose option D (index 3) as the correct
                # answer.  In a real question set you would determine this based on
                # the narrative logic of the sentences.
                "answer": 3,
            },
            {
                "question": """
                文章の空欄に入る最も適切なものを選びなさい。<br><br>
                社会における組織の役割は、時代とともに変化する。特に、大規模な企業や官公庁では、◎を図るために、部門ごとに明確な役割が定められている。しかし、急速な社会変化に対応するには、◉が求められる場面も多い。
                """,
                "options": [
                    "分業化 ◎効率性",
                    "分業化 ◎柔軟性",
                    "分業化 ◎統制",
                    "権限集中 ◎効率性",
                    "権限集中 ◎柔軟性",
                    "権限集中 ◎統制",
                ],
                # For demonstration we mark "分業化 ◎柔軟性" (index 1) as the correct answer.
                "answer": 1,
            },
        ],
        # Non‑verbal example set.  Replace with your own numeric
        # reasoning questions.  These remain unchanged from the
        # original example for brevity.
        "easy_nonverbal": [
            {
                "question": "数字 1〜100 のうち偶数は何個ありますか？",
                "options": ["50", "25", "100"],
                "answer": 0,
            },
            {
                "question": "1 + 2 × 3 = ?",
                "options": ["9", "7", "6"],
                "answer": 1,
            },
            {
                "question": "次のうち最も大きい数はどれ？",
                "options": ["√2", "3/2", "1.5"],
                "answer": 0,
            },
            {
                "question": "5本の指の中で真ん中は何番目？",
                "options": ["1", "3", "5"],
                "answer": 1,
            },
            {
                "question": "1から10までの総和はいくつ？",
                "options": ["45", "55", "60"],
                "answer": 1,
            },
        ],
        # English example set (basic vocabulary).  These remain
        # unchanged from the original example.
        "easy_english": [
            {
                "question": "Choose the correct synonym for 'rapid'.",
                "options": ["slow", "quick", "weak"],
                "answer": 1,
            },
            {
                "question": "What is the opposite of 'import'?",
                "options": ["export", "transport", "support"],
                "answer": 0,
            },
            {
                "question": "Select the word that best fits: 'She ____ the opportunity.'",
                "options": ["passed", "grasped", "wasted"],
                "answer": 1,
            },
            {
                "question": "Which word means 'to decrease'?",
                "options": ["diminish", "acquire", "enhance"],
                "answer": 0,
            },
            {
                "question": "Find the synonym for 'content'.",
                "options": ["unhappy", "satisfied", "worried"],
                "answer": 1,
            },
        ],
    }

    # Utility to load a question set by id.  If the id is not
    # recognized, a KeyError will be raised.
    def load_question_set(question_set_id: str) -> List[Dict[str, Any]]:
        return QUESTION_SETS[question_set_id]

    # Human‑readable labels for modes and categories.  These are used
    # when rendering exam pages to display the current subject (e.g.
    # "かんたん受験 - 言語").  Extend these dictionaries if you add
    # additional modes or categories.
    MODE_LABELS = {
        "easy": "かんたん受験",
        "full": "本番受験",
    }
    CATEGORY_LABELS = {
        "language": "言語",
        "nonverbal": "非言語",
        "english": "英語",
    }

    @app.route("/")
    def home() -> str:
        """Home page: redirect to exam selection."""
        return redirect(url_for("select_mode"))

    @app.route("/exam/select-mode")
    def select_mode() -> str:
        """Let users choose between different exam modes."""
        return render_template("select_mode.html")

    @app.route("/exam/select-category/<mode>")
    def select_category(mode: str) -> str:
        """Let users choose a category within a given mode.

        Only 'easy' mode is implemented for this example.  In a
        real application you would branch on `mode` and load
        appropriate question sets (e.g. full exam with more
        questions).
        """
        # Validate mode
        if mode not in {"easy"}:
            flash("未知の受験モードが指定されました。", "error")
            return redirect(url_for("select_mode"))
        return render_template("select_category.html", mode=mode)

    @app.route("/exam/pre-exam/<category>")
    def pre_exam(category: str) -> str:
        """Show exam description and start button for a given category.

        The category corresponds to a key prefix in the QUESTION_SETS
        dictionary (e.g. 'easy_language' → category 'language').  We
        assemble the question_set_id from the current mode (stored
        temporarily in a query parameter) and the category name.
        """
        mode = request.args.get("mode", "easy")
        question_set_id = f"{mode}_{category}"
        if question_set_id not in QUESTION_SETS:
            flash("選択されたカテゴリの問題セットが存在しません。", "error")
            return redirect(url_for("select_mode"))
        # Provide metadata for template.  In a more complex system
        # these values could be stored alongside the question set.
        info = {
            "title": f"かんたん受験 - {category}",
            "mode": mode,
            "category": category,
            "question_set_id": question_set_id,
            "num_questions": len(QUESTION_SETS[question_set_id]),
            "time_limit_minutes": len(QUESTION_SETS[question_set_id]),  # e.g. 1 min per question
        }
        return render_template("pre_exam.html", info=info)

    @app.post("/exam/start")
    def exam_start() -> Any:
        """Begin the exam by initializing session state."""
        question_set_id = request.form.get("question_set_id")
        if not question_set_id or question_set_id not in QUESTION_SETS:
            flash("無効な問題セットです。", "error")
            return redirect(url_for("select_mode"))
        # Initialize session data
        session.permanent = True
        session["question_set_id"] = question_set_id
        session["current_index"] = 0
        session["answers"] = []
        return redirect(url_for("exam_question"))

    @app.route("/exam/question")
    def exam_question() -> Any:
        """Display the current question or redirect to results."""
        question_set_id = session.get("question_set_id")
        index = session.get("current_index", 0)
        if not question_set_id:
            flash("受験が開始されていません。", "error")
            return redirect(url_for("select_mode"))
        questions = load_question_set(question_set_id)
        if index >= len(questions):
            return redirect(url_for("exam_result"))
        question = questions[index]
        # Provide simple per‑question timer value (60 seconds) to template
        time_limit = 60
        # Compute a human readable subject title from the question set id.
        # For example "easy_language" → "かんたん受験 - 言語".
        try:
            mode_key, category_key = question_set_id.split("_", 1)
        except ValueError:
            mode_key, category_key = question_set_id, ""
        subject_title = f"{MODE_LABELS.get(mode_key, mode_key)}"
        if category_key:
            subject_title += f" - {CATEGORY_LABELS.get(category_key, category_key)}"
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
        """Process the user's answer and advance to the next question."""
        selected = request.form.get("option")
        question_set_id = session.get("question_set_id")
        index = session.get("current_index", 0)
        if not question_set_id:
            flash("セッションが無効です。", "error")
            return redirect(url_for("select_mode"))
        questions = load_question_set(question_set_id)
        # Record the answer (convert to int or None)
        try:
            selected_index = int(selected) if selected is not None else None
        except (TypeError, ValueError):
            selected_index = None
        answers: List[int | None] = session.get("answers", [])
        # Extend the list if necessary
        if len(answers) <= index:
            answers.append(selected_index)
        else:
            answers[index] = selected_index
        session["answers"] = answers
        # Advance to next question
        session["current_index"] = index + 1
        return redirect(url_for("exam_question"))

    @app.route("/exam/result")
    def exam_result() -> str:
        """Display the result summary."""
        question_set_id = session.get("question_set_id")
        answers = session.get("answers", [])
        if not question_set_id:
            flash("結果を表示できません。", "error")
            return redirect(url_for("select_mode"))
        questions = load_question_set(question_set_id)
        # Compute score
        score = 0
        for idx, q in enumerate(questions):
            if idx < len(answers) and answers[idx] is not None and answers[idx] == q["answer"]:
                score += 1
        # Clear session to allow a new exam
        session.pop("question_set_id", None)
        session.pop("current_index", None)
        session.pop("answers", None)
        return render_template("results.html", total=len(questions), score=score)

    # API endpoint for checking server status (optional)
    @app.route("/api/status")
    def api_status() -> Any:
        return jsonify({"status": "ok"})

    @app.context_processor
    def inject_now() -> Dict[str, Any]:
        """Inject current year into all templates."""
        from datetime import datetime
        return {"current_year": datetime.now().year}

    return app


if __name__ == "__main__":
    app = create_app()
    # Enable debug mode for development convenience.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)