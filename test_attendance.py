from models import db, User, Subject, AttendanceRecord
from datetime import date
from services.attendance_service import attendance_summary

def test_attendance_percentage_and_projection(app):
    with app.app_context():
        user = User(username="Test", email="test@example.com")
        user.set_password("strongpass123")
        db.session.add(user); db.session.flush()
        subject = Subject(user_id=user.id, subject_name="Statistics", minimum_attendance_percentage=75)
        db.session.add(subject); db.session.flush()
        for status in ["Present", "Present", "Absent", "Present"]:
            db.session.add(AttendanceRecord(user_id=user.id, subject_id=subject.id, class_date=date.today(),
                status=status, topic_covered="Probability"))
        db.session.commit()
        result = attendance_summary(subject)
        assert result["total"] == 4
        assert result["attended"] == 3
        assert result["percentage"] == 75.0
        assert result["classes_to_target"] == 0
