from models import db, User, Subject, StudyNote

def test_note_persists_in_database(app):
    with app.app_context():
        user = User(username="Test", email="notes@example.com")
        user.set_password("strongpass123")
        db.session.add(user); db.session.flush()
        subject = Subject(user_id=user.id, subject_name="AI")
        db.session.add(subject); db.session.flush()
        note = StudyNote(user_id=user.id, subject_id=subject.id, topic_title="Search", note_content="Breadth-first search.")
        db.session.add(note); db.session.commit()
        assert StudyNote.query.filter_by(user_id=user.id, topic_title="Search").first().note_content == "Breadth-first search."
