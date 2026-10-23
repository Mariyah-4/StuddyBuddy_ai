from models import User

def register(client, email="student@example.com"):
    return client.post("/register", data={
        "username": "Student", "email": email,
        "password": "strongpass123", "confirm_password": "strongpass123"
    }, follow_redirects=True)

def test_registration_hashes_password(client, app):
    response = register(client)
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="student@example.com").first()
        assert user is not None
        assert user.password_hash != "strongpass123"
        assert user.check_password("strongpass123")

def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code in (302, 401)
