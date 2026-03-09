import re

def get_task_id(response, action="update"):
    """Extract task ID from HTML for a given action (update/delete)."""
    match = re.search(rf'/{action}/(\d+)', response.data.decode())
    return int(match.group(1)) if match else None


def test_add_task(client):
    client.post('/login', data={'username': 'testuser', 'password': 'testpass'})
    response = client.post('/add', data={'task': 'Run'})
    assert response.status_code == 302

    response = client.get('/')
    assert b'Run' in response.data


def test_update_task(client):
    client.post('/login', data={'username': 'testuser', 'password': 'testpass'})
    client.post('/add', data={'task': 'Jog'})
    response = client.get('/')
    task_id = get_task_id(response, "update")
    assert task_id is not None

    response = client.post(f'/update/{task_id}', data={'task': 'Jogging'})
    assert response.status_code == 302

    response = client.get('/')
    assert b'Jogging' in response.data


def test_toggle_task(client):
    client.post('/login', data={'username': 'testuser', 'password': 'testpass'})
    client.post('/add', data={'task': 'Run'})
    response = client.get('/')
    task_id = get_task_id(response, "toggle")
    assert task_id is not None

    response = client.post(f'/toggle/{task_id}')
    assert response.status_code == 302

    response = client.get('/')
    assert b'Completed' in response.data


def test_delete_task(client):
    client.post('/login', data={'username': 'testuser', 'password': 'testpass'})
    client.post('/add', data={'task': 'Swim'})
    response = client.get('/')
    task_id = get_task_id(response, "delete")
    assert task_id is not None

    response = client.get(f'/delete/{task_id}')
    assert response.status_code == 302

    response = client.get('/')
    assert b'Swim' not in response.data