"""Demo assignments and questions for seed_demo (SPEC 10): three
assignments of the demo teacher, in the batch and subject the demo student
also takes, six questions in the demo teacher's bank, and three quizzes
from them: one live now, one exam opening in 2 days, and one closed exam
with attempts (one graded, one waiting for marks with an exam flag)
(SPEC 10).

- one open for a week, which the demo student has not answered yet;
- one due tomorrow, answered by the demo student and waiting for marks;
- one closed two days ago: the demo student's answer is graded, one other
  answer waits for marks, and the rest of the class missed it.

The services refuse a due time in the past, so the closed assignment is
made open and then moved back (still inside the tenant context).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.assessments.models import (
    Assignment,
    AttemptEventKind,
    Question,
    QuestionKind,
    Quiz,
    QuizAttempt,
    QuizKind,
    Submission,
)
from apps.assessments.services import (
    AssignmentDetails,
    QuestionDetails,
    QuizDetails,
    add_questions,
    create_assignment,
    create_quiz,
    grade_submission,
    log_attempt_event,
    mark_attempt,
    publish_quiz,
    quiz_results,
    save_attempt,
    save_question,
    short_items,
    start_attempt,
    submission_rows,
    submit_answer,
)
from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute
from apps.lectures.demo import shared_link
from apps.people.demo import DEMO_STUDENT_EMAIL, DEMO_TEACHER_EMAIL
from apps.people.models import TeacherProfile

INSTRUCTIONS = (
    "Read the notes from this week's classes.\n"
    "Answer every question in full sentences and show your working."
)


def seed_assignments(institute: Institute) -> None:
    """Add the demo assignments once (a second run adds nothing)."""
    with tenant_context(institute):
        teacher = TeacherProfile.objects.filter(user__email=DEMO_TEACHER_EMAIL).first()
        if teacher is None or Assignment.objects.filter(teacher=teacher).exists():
            return
        link = shared_link(teacher)
        if link is None:
            return
        now = timezone.now()
        name = link.subject.name

        def add(title: str, days: float, marks: int) -> Assignment:
            details = AssignmentDetails(
                title=title,
                instructions=INSTRUCTIONS,
                teacher=teacher,
                batch=link.batch,
                subject=link.subject,
                total_marks=marks,
                due_at=now + timedelta(days=days),
            )
            return create_assignment(institute, details)

        questions = _seed_questions(institute, teacher, link.subject)
        _seed_quizzes(institute, teacher, link, questions, now)
        add(f"{name} project", 7, 20)
        tomorrow = add(f"{name} practice sheet", 1, 10)
        closed = add(f"{name} chapter questions", 1, 10)
        _seed_answers(tomorrow, closed, teacher, now)


def _seed_answers(tomorrow, closed, teacher, now) -> None:
    students = [row.student for row in submission_rows(closed)]
    demo = next((s for s in students if s.user.email == DEMO_STUDENT_EMAIL), None)
    others = [student for student in students if student != demo]
    if demo is not None:
        submit_answer(tomorrow, demo, "Question 1: 12. Question 2: 3/4.")
        graded = submit_answer(closed, demo, "My answers are in order 1 to 5.")
        grade_submission(
            graded,
            Decimal("8.5"),
            "Good work. Check the units in question 4.",
            graded_by=teacher.user,
        )
    if others:
        submit_answer(closed, others[0], "Answers 1 to 4. I could not do 5.")
    due = now - timedelta(days=2)
    Assignment.objects.filter(pk=closed.pk).update(due_at=due)
    Submission.objects.filter(assignment=closed).update(
        submitted_at=due - timedelta(hours=3)
    )


# (kind, text, marks, options, index of the correct option)
QUESTIONS = (
    (QuestionKind.MCQ, "Which of these numbers is prime?", 1, ("4", "7", "9"), 1),
    (QuestionKind.MCQ, "What is 15% of 200?", 2, ("15", "30", "35", "45"), 1),
    (QuestionKind.MCQ, "Is 0.5 the same as 1/2?", 1, ("Yes", "No"), 0),
    (
        QuestionKind.MCQ,
        "Which unit is used for time?",
        1,
        ("Metre", "Second", "Kilogram", "Ampere", "Kelvin", "Mole"),
        1,
    ),
    (QuestionKind.SHORT, "Explain in two sentences what an average is.", 3, (), None),
    (QuestionKind.SHORT, "Write one rule you use to check your answers.", 2, (), None),
)


def _seed_questions(institute: Institute, teacher, subject) -> list[Question]:
    saved = []
    for kind, text, marks, options, correct in QUESTIONS:
        details = QuestionDetails(
            teacher=teacher,
            subject=subject,
            kind=kind,
            text=text,
            marks=marks,
            options=options,
            correct=correct,
        )
        saved.append(save_question(institute, details))
    return saved


def _seed_quizzes(institute: Institute, teacher, link, questions, now) -> None:
    """Both published; the live one is moved back to have opened 5 minutes
    ago (the services refuse a past opening)."""
    for title, kind, days, chosen in (
        (f"{link.subject.name} weekly quiz", QuizKind.QUIZ, 1, questions[:3]),
        (f"{link.subject.name} term exam", QuizKind.EXAM, 2, questions),
    ):
        quiz = create_quiz(
            institute,
            QuizDetails(
                title=title,
                kind=kind,
                teacher=teacher,
                batch=link.batch,
                subject=link.subject,
                opens_at=now + timedelta(days=days),
                duration_minutes=30 if kind == QuizKind.QUIZ else 60,
                require_full_screen=kind == QuizKind.EXAM,
                flag_tab_leaving=kind == QuizKind.EXAM,
            ),
        )
        add_questions(quiz, chosen)
        publish_quiz(quiz)
        if kind == QuizKind.QUIZ:
            Quiz.objects.filter(pk=quiz.pk).update(opens_at=now - timedelta(minutes=5))
    _seed_closed_quiz(institute, teacher, link, questions[:5], now)


def _seed_closed_quiz(institute: Institute, teacher, link, questions, now) -> None:
    """An exam in exam mode that closed 3 days ago (moved back like the
    live quiz). The demo student's attempt is graded; one other attempt
    waits for marks and left the page once."""
    quiz = create_quiz(
        institute,
        QuizDetails(
            title=f"{link.subject.name} unit exam",
            kind=QuizKind.EXAM,
            teacher=teacher,
            batch=link.batch,
            subject=link.subject,
            opens_at=now + timedelta(days=1),
            duration_minutes=20,
            require_full_screen=True,
            flag_tab_leaving=True,
        ),
    )
    add_questions(quiz, questions)
    publish_quiz(quiz)
    opens = now - timedelta(days=3)
    Quiz.objects.filter(pk=quiz.pk).update(opens_at=opens)
    quiz.refresh_from_db()
    students = [row.student for row in quiz_results(quiz, now=now)]
    demo = next((s for s in students if s.user.email == DEMO_STUDENT_EMAIL), None)
    others = [student for student in students if student != demo]
    takers = ([demo] if demo else []) + others[:1]
    for number, student in enumerate(takers):
        start = opens + timedelta(minutes=2 + number)
        attempt = start_attempt(quiz, student, now=start)
        if student != demo:
            log_attempt_event(
                attempt, AttemptEventKind.LEFT_PAGE, now=start + timedelta(minutes=5)
            )
        items = {item.question.text: item for item in quiz.items.all()}
        answers = {}
        for question in questions:
            item = items[question.text]
            if question.kind == QuestionKind.SHORT:
                answers[item.pk] = (
                    "The sum of the values divided by how many there are."
                )
            else:
                options = list(question.options.all())
                answers[item.pk] = options[number % len(options)].pk
        attempt = save_attempt(
            attempt, answers, submit=True, now=start + timedelta(minutes=12)
        )
        if student == demo:
            mark_attempt(
                attempt, {item.pk: Decimal("2.5") for _n, item in short_items(attempt)}
            )


def reset_assignments(institute: Institute) -> int:
    """Delete the institute's answers, assignments, quizzes and questions
    (before its people).

    Uses ``unscoped`` on purpose: a management command, one institute.
    """
    # unscoped: seed_demo --reset, limited to the demo institute (their
    # answers go with them; an attempt keeps its quiz, so it goes first).
    attempts, _ = QuizAttempt.unscoped.filter(institute=institute).delete()
    # unscoped: seed_demo --reset, limited to the demo institute.
    answers, _ = Submission.unscoped.filter(institute=institute).delete()
    # unscoped: seed_demo --reset, limited to the demo institute.
    assignments, _ = Assignment.unscoped.filter(institute=institute).delete()
    # unscoped: seed_demo --reset, limited to the demo institute (their
    # questions in the quiz go with them).
    quizzes, _ = Quiz.unscoped.filter(institute=institute).delete()
    # unscoped: seed_demo --reset, limited to the demo institute (the
    # options go with their questions).
    questions, _ = Question.unscoped.filter(institute=institute).delete()
    return attempts + answers + assignments + quizzes + questions
