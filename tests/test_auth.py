def test_register_and_login(client):
    # Register
    response = client.post('/register', data={'username': 'testuser', 'password': 'testpass'})
    assert response.status_code == 302  # redirect after success

    # Login
    response = client.post('/login', data={'username': 'testuser', 'password': 'testpass'})
    assert response.status_code == 302
