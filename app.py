import os
import uuid
from datetime import datetime, date
from pathlib import Path
from io import BytesIO
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, flash, abort, current_app, send_file, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from werkzeug.utils import secure_filename
from sqlalchemy import func
from config import Config
from models import db, User, Subject, AttendanceRecord, Syllabus, StudyNote, ChatConversation, ChatMessage, StudyTask
from services.syllabus_service import extract_text, ALLOWED_EXTENSIONS
from services.ai_service import generate_notes, answer_question
from services.attendance_service import attendance_summary

load_dotenv()

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    login_manager = LoginManager(app)
    login_manager.login_view = "login"
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_globals():
        return {"today": date.today()}

    with app.app_context():
        db.create_all()

    def owned_subject(subject_id):
        subject = db.session.get(Subject, subject_id)
        if not subject or subject.user_id != current_user.id:
            abort(404)
        return subject

    def owned_syllabus(syllabus_id):
        syllabus = db.session.get(Syllabus, syllabus_id)
        if not syllabus or syllabus.user_id != current_user.id:
            abort(404)
        return syllabus

    def owned_note(note_id):
        note = db.session.get(StudyNote, note_id)
        if not note or note.user_id != current_user.id:
            abort(404)
        return note

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        form = RegisterForm()
        if form.validate_on_submit():
            email = form.email.data.strip().lower()
            if User.query.filter_by(email=email).first():
                flash("An account with that email already exists.", "danger")
            else:
                user = User(username=form.username.data.strip(), email=email)
                user.set_password(form.password.data)
                db.session.add(user)
                db.session.commit()
                login_user(user)
                flash("Welcome to StudySync AI! Your account is ready.", "success")
                return redirect(url_for("dashboard"))
        return render_template("register.html", form=form)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data.strip().lower()).first()
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember.data)
                return redirect(request.args.get("next") or url_for("dashboard"))
            flash("Email or password is incorrect.", "danger")
        return render_template("login.html", form=form)

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.subject_name).all()
        records = AttendanceRecord.query.filter_by(user_id=current_user.id).order_by(AttendanceRecord.class_date.desc()).limit(6).all()
        notes = StudyNote.query.filter_by(user_id=current_user.id).order_by(StudyNote.updated_at.desc()).limit(4).all()
        syllabi = Syllabus.query.filter_by(user_id=current_user.id).order_by(Syllabus.upload_date.desc()).limit(4).all()
        tasks = StudyTask.query.filter_by(user_id=current_user.id, is_completed=False).order_by(StudyTask.due_date.asc()).limit(5).all()
        total = sum(s.total_classes for s in subjects)
        attended = sum(s.classes_attended for s in subjects)
        return render_template("dashboard.html", subjects=subjects, records=records, notes=notes,
                               syllabi=syllabi, tasks=tasks, total=total, attended=attended,
                               overall=round(attended*100/total, 1) if total else 0)

    @app.route("/subjects", methods=["GET", "POST"])
    @login_required
    def subjects():
        if request.method == "POST":
            name = request.form.get("subject_name", "").strip()
            code = request.form.get("subject_code", "").strip()
            faculty = request.form.get("faculty_name", "").strip()
            try:
                target = float(request.form.get("minimum_attendance_percentage", "75"))
                if not name or not 0 <= target <= 100:
                    raise ValueError
            except ValueError:
                flash("Enter a subject name and a target attendance between 0 and 100.", "danger")
            else:
                db.session.add(Subject(user_id=current_user.id, subject_name=name, subject_code=code,
                                       faculty_name=faculty, minimum_attendance_percentage=target))
                db.session.commit()
                flash("Subject added.", "success")
                return redirect(url_for("subjects"))
        items = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.subject_name).all()
        return render_template("subjects.html", subjects=items)

    @app.route("/subjects/<int:subject_id>/edit", methods=["POST"])
    @login_required
    def subject_edit(subject_id):
        subject = owned_subject(subject_id)
        name = request.form.get("subject_name", "").strip()
        try:
            target = float(request.form.get("minimum_attendance_percentage", "75"))
            if not name or not 0 <= target <= 100: raise ValueError
        except ValueError:
            flash("Please provide a valid name and attendance target.", "danger")
        else:
            subject.subject_name = name
            subject.subject_code = request.form.get("subject_code", "").strip()
            subject.faculty_name = request.form.get("faculty_name", "").strip()
            subject.minimum_attendance_percentage = target
            db.session.commit()
            flash("Subject updated.", "success")
        return redirect(url_for("subjects"))

    @app.route("/subjects/<int:subject_id>/delete", methods=["POST"])
    @login_required
    def subject_delete(subject_id):
        subject = owned_subject(subject_id)
        db.session.delete(subject)
        db.session.commit()
        flash("Subject and its related records were deleted.", "info")
        return redirect(url_for("subjects"))

    @app.route("/attendance", methods=["GET", "POST"])
    @login_required
    def attendance():
        subjects_list = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.subject_name).all()
        if request.method == "POST":
            try:
                subject = owned_subject(int(request.form.get("subject_id", "0")))
                class_date = date.fromisoformat(request.form.get("class_date", ""))
                status = request.form.get("status", "")
                topic = request.form.get("topic_covered", "").strip()
                if status not in {"Present", "Absent"} or not topic:
                    raise ValueError
                record = AttendanceRecord(user_id=current_user.id, subject_id=subject.id, class_date=class_date,
                    status=status, topic_covered=topic, class_notes=request.form.get("class_notes", "").strip(),
                    faculty_name=request.form.get("faculty_name", "").strip())
                db.session.add(record)
                db.session.commit()
                flash("Class attendance saved.", "success")
                return redirect(url_for("attendance"))
            except (ValueError, TypeError):
                flash("Check the subject, date, attendance status, and topic fields.", "danger")
        q = AttendanceRecord.query.filter_by(user_id=current_user.id)
        subject_filter = request.args.get("subject", type=int)
        status_filter = request.args.get("status", "")
        start = request.args.get("start", "")
        end = request.args.get("end", "")
        if subject_filter:
            q = q.filter_by(subject_id=subject_filter)
        if status_filter in {"Present", "Absent"}:
            q = q.filter_by(status=status_filter)
        if start:
            try: q = q.filter(AttendanceRecord.class_date >= date.fromisoformat(start))
            except ValueError: pass
        if end:
            try: q = q.filter(AttendanceRecord.class_date <= date.fromisoformat(end))
            except ValueError: pass
        records = q.order_by(AttendanceRecord.class_date.desc(), AttendanceRecord.id.desc()).all()
        return render_template("attendance.html", subjects=subjects_list, records=records,
                               subject_filter=subject_filter, status_filter=status_filter, start=start, end=end)

    @app.route("/attendance/<int:record_id>/edit", methods=["POST"])
    @login_required
    def attendance_edit(record_id):
        record = db.session.get(AttendanceRecord, record_id)
        if not record or record.user_id != current_user.id: abort(404)
        try:
            subject = owned_subject(int(request.form.get("subject_id", "0")))
            class_date = date.fromisoformat(request.form.get("class_date", ""))
            status = request.form.get("status", "")
            topic = request.form.get("topic_covered", "").strip()
            if status not in {"Present", "Absent"} or not topic: raise ValueError
            record.subject_id, record.class_date, record.status, record.topic_covered = subject.id, class_date, status, topic
            record.class_notes = request.form.get("class_notes", "").strip()
            record.faculty_name = request.form.get("faculty_name", "").strip()
            db.session.commit()
            flash("Attendance record updated.", "success")
        except (ValueError, TypeError):
            flash("Could not update the record. Check all required fields.", "danger")
        return redirect(url_for("attendance"))

    @app.route("/attendance/<int:record_id>/delete", methods=["POST"])
    @login_required
    def attendance_delete(record_id):
        record = db.session.get(AttendanceRecord, record_id)
        if not record or record.user_id != current_user.id: abort(404)
        db.session.delete(record); db.session.commit()
        flash("Attendance record deleted.", "info")
        return redirect(url_for("attendance"))

    @app.route("/syllabus/upload", methods=["GET", "POST"])
    @login_required
    def syllabus_upload():
        subjects_list = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.subject_name).all()
        if request.method == "POST":
            file = request.files.get("file")
            try:
                subject_id = int(request.form.get("subject_id", "0"))
                subject = owned_subject(subject_id)
                if not file or not file.filename:
                    raise ValueError("Choose a syllabus file first.")
                original = secure_filename(file.filename)
                ext = Path(original).suffix.lower()
                if ext not in ALLOWED_EXTENSIONS:
                    raise ValueError("Only PDF, DOCX, and TXT files are supported.")
                stored = f"{uuid.uuid4().hex}{ext}"
                path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored)
                file.save(path)
                try:
                    extracted = extract_text(path)
                    if not extracted:
                        raise ValueError("No readable text was found in the document.")
                except Exception:
                    if os.path.exists(path): os.remove(path)
                    raise
                syllabus = Syllabus(user_id=current_user.id, subject_id=subject.id, original_filename=original,
                    stored_filename=stored, extracted_text=extracted,
                    academic_semester=request.form.get("academic_semester", "").strip(), processing_status="Extracted")
                db.session.add(syllabus); db.session.commit()
                flash("Syllabus uploaded and text extracted successfully.", "success")
                # Automatically generate notes when configured; if AI fails, preserve the upload.
                if current_app.config.get("OPENAI_API_KEY"):
                    try:
                        create_notes_for_syllabus(syllabus)
                        flash("AI notes were generated and saved.", "success")
                    except Exception as exc:
                        syllabus.processing_status = "AI failed — retry available"
                        db.session.commit()
                        flash(f"Syllabus saved, but note generation failed: {str(exc)[:180]}", "warning")
                else:
                    flash("To auto-generate notes, add OPENAI_API_KEY to your .env file.", "info")
                return redirect(url_for("syllabus_detail", syllabus_id=syllabus.id))
            except (ValueError, TypeError) as exc:
                flash(str(exc) or "Please check the upload form.", "danger")
        return render_template("upload_syllabus.html", subjects=subjects_list)

    def create_notes_for_syllabus(syllabus):
        notes = generate_notes(syllabus.subject.subject_name, syllabus.extracted_text)
        # Make retries idempotent for this syllabus: replace previously generated entries.
        StudyNote.query.filter_by(user_id=current_user.id, syllabus_id=syllabus.id, note_type="AI Study Notes").delete()
        for item in notes:
            db.session.add(StudyNote(user_id=current_user.id, subject_id=syllabus.subject_id,
                syllabus_id=syllabus.id, unit_title=item["unit_title"], topic_title=item["topic_title"],
                note_content=item["note_content"], note_type="AI Study Notes"))
        syllabus.processing_status = "Completed"
        db.session.commit()

    @app.route("/syllabus/<int:syllabus_id>")
    @login_required
    def syllabus_detail(syllabus_id):
        syllabus = owned_syllabus(syllabus_id)
        return render_template("syllabus_detail.html", syllabus=syllabus)

    @app.route("/syllabus/<int:syllabus_id>/generate-notes", methods=["POST"])
    @login_required
    def syllabus_generate(syllabus_id):
        syllabus = owned_syllabus(syllabus_id)
        try:
            create_notes_for_syllabus(syllabus)
            flash("Notes generated and saved.", "success")
        except Exception as exc:
            syllabus.processing_status = "AI failed — retry available"
            db.session.commit()
            flash(f"Could not generate notes: {str(exc)[:200]}", "danger")
        return redirect(url_for("syllabus_detail", syllabus_id=syllabus.id))

    @app.route("/syllabus/<int:syllabus_id>/delete", methods=["POST"])
    @login_required
    def syllabus_delete(syllabus_id):
        syllabus = owned_syllabus(syllabus_id)
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], syllabus.stored_filename)
        db.session.delete(syllabus); db.session.commit()
        if os.path.exists(path): os.remove(path)
        flash("Syllabus deleted.", "info")
        return redirect(url_for("syllabus_upload"))

    @app.route("/notes")
    @login_required
    def notes():
        q = StudyNote.query.filter_by(user_id=current_user.id)
        search = request.args.get("q", "").strip()
        subject_id = request.args.get("subject", type=int)
        if search:
            q = q.filter(db.or_(StudyNote.topic_title.ilike(f"%{search}%"),
                                StudyNote.unit_title.ilike(f"%{search}%"),
                                StudyNote.note_content.ilike(f"%{search}%")))
        if subject_id:
            q = q.filter_by(subject_id=subject_id)
        items = q.order_by(StudyNote.is_favorite.desc(), StudyNote.updated_at.desc()).all()
        return render_template("notes.html", notes=items, subjects=Subject.query.filter_by(user_id=current_user.id).all(), q=search, subject_filter=subject_id)

    @app.route("/notes/<int:note_id>")
    @login_required
    def note_detail(note_id):
        note = owned_note(note_id)
        return render_template("note_detail.html", note=note)

    @app.route("/notes/<int:note_id>/edit", methods=["POST"])
    @login_required
    def note_edit(note_id):
        note = owned_note(note_id)
        title = request.form.get("topic_title", "").strip()
        content = request.form.get("note_content", "").strip()
        if not title or not content:
            flash("Title and note content are required.", "danger")
        else:
            note.topic_title, note.note_content = title, content
            note.updated_at = datetime.utcnow()
            db.session.commit()
            flash("Note updated.", "success")
        return redirect(url_for("note_detail", note_id=note.id))

    @app.route("/notes/<int:note_id>/favorite", methods=["POST"])
    @login_required
    def note_favorite(note_id):
        note = owned_note(note_id)
        note.is_favorite = not note.is_favorite
        db.session.commit()
        return redirect(request.referrer or url_for("notes"))

    @app.route("/notes/<int:note_id>/delete", methods=["POST"])
    @login_required
    def note_delete(note_id):
        note = owned_note(note_id)
        db.session.delete(note); db.session.commit()
        flash("Note deleted.", "info")
        return redirect(url_for("notes"))

    @app.route("/notes/<int:note_id>/download/<kind>")
    @login_required
    def note_download(note_id, kind):
        note = owned_note(note_id)
        if kind not in {"txt", "pdf"}: abort(404)
        filename = secure_filename(note.topic_title) or "study-note"
        if kind == "txt":
            data = f"{note.topic_title}\n{note.unit_title}\n\n{note.note_content}".encode("utf-8")
            return send_file(BytesIO(data), as_attachment=True, download_name=f"{filename}.txt", mimetype="text/plain")
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from xml.sax.saxutils import escape
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()
        story = [Paragraph(escape(note.topic_title), styles["Title"]), Paragraph(escape(note.unit_title), styles["Heading2"]), Spacer(1, 12)]
        for line in note.note_content.splitlines():
            if line.strip():
                story.append(Paragraph(escape(line).replace("&lt;strong&gt;", ""), styles["BodyText"]))
                story.append(Spacer(1, 5))
        doc.build(story); buf.seek(0)
        return send_file(buf, as_attachment=True, download_name=f"{filename}.pdf", mimetype="application/pdf")

    @app.route("/chat", methods=["GET", "POST"])
    @login_required
    def chat():
        conversations = ChatConversation.query.filter_by(user_id=current_user.id).order_by(ChatConversation.updated_at.desc()).all()
        conversation_id = request.args.get("conversation", type=int)
        conversation = None
        if conversation_id:
            conversation = ChatConversation.query.filter_by(id=conversation_id, user_id=current_user.id).first_or_404()
        elif conversations:
            conversation = conversations[0]
        if request.method == "POST":
            question = request.form.get("message", "").strip()
            selected_subject = request.form.get("subject_id", type=int)
            conv_id = request.form.get("conversation_id", type=int)
            if not question:
                flash("Type a question first.", "warning")
                return redirect(url_for("chat", conversation=conv_id) if conv_id else url_for("chat"))
            if conv_id:
                conversation = ChatConversation.query.filter_by(id=conv_id, user_id=current_user.id).first_or_404()
            else:
                conversation = ChatConversation(user_id=current_user.id, title=question[:70])
                db.session.add(conversation); db.session.commit()
            context = ""
            if selected_subject:
                subject = owned_subject(selected_subject)
                syllabus = Syllabus.query.filter_by(user_id=current_user.id, subject_id=subject.id).order_by(Syllabus.upload_date.desc()).first()
                notes_for_subject = StudyNote.query.filter_by(user_id=current_user.id, subject_id=subject.id).order_by(StudyNote.updated_at.desc()).limit(5).all()
                context = f"Subject: {subject.subject_name}\n"
                if syllabus: context += "Syllabus excerpt:\n" + syllabus.extracted_text[:7000] + "\n"
                for n in notes_for_subject: context += f"\nNote {n.topic_title}:\n{n.note_content[:1800]}\n"
            history = [{"role": m.role, "content": m.content} for m in conversation.messages[-8:]]
            db.session.add(ChatMessage(conversation_id=conversation.id, role="user", content=question))
            try:
                answer = answer_question(question, context=context, history=history)
            except Exception as exc:
                answer = f"AI service is unavailable: {str(exc)[:250]}\n\nYour question was saved. Check your API key and connection, then try again."
            db.session.add(ChatMessage(conversation_id=conversation.id, role="assistant", content=answer))
            conversation.updated_at = datetime.utcnow()
            db.session.commit()
            return redirect(url_for("chat", conversation=conversation.id))
        return render_template("chat.html", conversations=conversations, conversation=conversation,
                               subjects=Subject.query.filter_by(user_id=current_user.id).all())

    @app.route("/chat/new", methods=["POST"])
    @login_required
    def chat_new():
        conv = ChatConversation(user_id=current_user.id, title="New study conversation")
        db.session.add(conv); db.session.commit()
        return redirect(url_for("chat", conversation=conv.id))

    @app.route("/chat/<int:conversation_id>/rename", methods=["POST"])
    @login_required
    def chat_rename(conversation_id):
        conv = ChatConversation.query.filter_by(id=conversation_id, user_id=current_user.id).first_or_404()
        title = request.form.get("title", "").strip()
        if title: conv.title = title[:160]; db.session.commit()
        return redirect(url_for("chat", conversation=conv.id))

    @app.route("/chat/<int:conversation_id>/delete", methods=["POST"])
    @login_required
    def chat_delete(conversation_id):
        conv = ChatConversation.query.filter_by(id=conversation_id, user_id=current_user.id).first_or_404()
        db.session.delete(conv); db.session.commit()
        flash("Conversation deleted.", "info")
        return redirect(url_for("chat"))

    @app.route("/planner", methods=["GET", "POST"])
    @login_required
    def planner():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            try:
                subject_id = request.form.get("subject_id", type=int)
                if subject_id: owned_subject(subject_id)
                due = date.fromisoformat(request.form["due_date"]) if request.form.get("due_date") else None
                if not title: raise ValueError
                task = StudyTask(user_id=current_user.id, subject_id=subject_id, title=title,
                    description=request.form.get("description", "").strip(), due_date=due)
                db.session.add(task); db.session.commit()
                flash("Study task added.", "success")
                return redirect(url_for("planner"))
            except (ValueError, TypeError):
                flash("Please enter a task title and valid deadline.", "danger")
        tasks = StudyTask.query.filter_by(user_id=current_user.id).order_by(StudyTask.is_completed, StudyTask.due_date.asc()).all()
        return render_template("planner.html", tasks=tasks, subjects=Subject.query.filter_by(user_id=current_user.id).all())

    @app.route("/planner/<int:task_id>/toggle", methods=["POST"])
    @login_required
    def task_toggle(task_id):
        task = db.session.get(StudyTask, task_id)
        if not task or task.user_id != current_user.id: abort(404)
        task.is_completed = not task.is_completed
        db.session.commit()
        return redirect(url_for("planner"))

    @app.route("/planner/<int:task_id>/delete", methods=["POST"])
    @login_required
    def task_delete(task_id):
        task = db.session.get(StudyTask, task_id)
        if not task or task.user_id != current_user.id: abort(404)
        db.session.delete(task); db.session.commit()
        flash("Task deleted.", "info")
        return redirect(url_for("planner"))

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            if username:
                current_user.username = username[:80]
                db.session.commit()
                flash("Profile updated.", "success")
            return redirect(url_for("profile"))
        return render_template("profile.html")

    @app.errorhandler(413)
    def too_large(_):
        flash("That file is too large. The upload limit is configured in .env.", "danger")
        return redirect(url_for("syllabus_upload"))

    @app.errorhandler(404)
    def not_found(_):
        return render_template("404.html"), 404

    return app

class RegisterForm(FlaskForm):
    username = StringField("Name", validators=[DataRequired(), Length(min=2, max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, message="Use at least 8 characters.")])
    confirm_password = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")])
    submit = SubmitField("Create account")

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit = SubmitField("Log in")

app = create_app()

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
