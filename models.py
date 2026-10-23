from datetime import datetime, date
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    subjects = db.relationship("Subject", backref="owner", cascade="all, delete-orphan")
    tasks = db.relationship("StudyTask", backref="owner", cascade="all, delete-orphan")
    conversations = db.relationship("ChatConversation", backref="owner", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    subject_name = db.Column(db.String(140), nullable=False)
    subject_code = db.Column(db.String(40), default="")
    faculty_name = db.Column(db.String(120), default="")
    minimum_attendance_percentage = db.Column(db.Float, default=75.0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    attendance_records = db.relationship("AttendanceRecord", backref="subject", cascade="all, delete-orphan")
    syllabi = db.relationship("Syllabus", backref="subject", cascade="all, delete-orphan")
    notes = db.relationship("StudyNote", backref="subject", cascade="all, delete-orphan")

    @property
    def total_classes(self):
        return len(self.attendance_records)

    @property
    def classes_attended(self):
        return sum(1 for r in self.attendance_records if r.status == "Present")

    @property
    def classes_missed(self):
        return self.total_classes - self.classes_attended

    @property
    def attendance_percentage(self):
        return round((self.classes_attended / self.total_classes) * 100, 1) if self.total_classes else 0.0

    @property
    def classes_to_target(self):
        """Consecutive classes to attend to reach the target; 0 if already there."""
        target = self.minimum_attendance_percentage / 100
        a, t = self.classes_attended, self.total_classes
        if t == 0 or (a / t) >= target:
            return 0
        if target >= 1:
            return max(0, 1_000_000) if a < t else 0
        return max(0, int(__import__("math").ceil((target * t - a) / (1 - target))))

class AttendanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False, index=True)
    class_date = db.Column(db.Date, nullable=False, default=date.today)
    status = db.Column(db.String(10), nullable=False)
    topic_covered = db.Column(db.String(240), nullable=False)
    class_notes = db.Column(db.Text, default="")
    faculty_name = db.Column(db.String(120), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Syllabus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    extracted_text = db.Column(db.Text, nullable=False, default="")
    academic_semester = db.Column(db.String(80), default="")
    upload_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    processing_status = db.Column(db.String(30), default="Extracted", nullable=False)
    notes = db.relationship("StudyNote", backref="syllabus", cascade="all, delete-orphan")

class StudyNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False, index=True)
    syllabus_id = db.Column(db.Integer, db.ForeignKey("syllabus.id"), nullable=True, index=True)
    unit_title = db.Column(db.String(240), default="General")
    topic_title = db.Column(db.String(240), nullable=False)
    note_content = db.Column(db.Text, nullable=False)
    note_type = db.Column(db.String(40), default="Study Notes")
    is_favorite = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class ChatConversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(160), default="New study conversation")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    messages = db.relationship("ChatMessage", backref="conversation", cascade="all, delete-orphan", order_by="ChatMessage.created_at")

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("chat_conversation.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class StudyTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=True, index=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, default="")
    due_date = db.Column(db.Date, nullable=True)
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    subject = db.relationship("Subject")
