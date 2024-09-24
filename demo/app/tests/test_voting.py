import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from app.models import ThreadModel
from playwright.sync_api import expect
import re

@pytest.fixture(scope="session")
def launch_arguments(launch_arguments):
    return [*launch_arguments, "--slow-mo=1000"]

@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(username='testuser', password='testpass')

@pytest.fixture
def user2(db):
    User = get_user_model()
    return User.objects.create_user(username='testuser2', password='testpass2')

@pytest.fixture
def user3(db):
    User = get_user_model()
    return User.objects.create_user(username='testuser3', password='testpass3')

@pytest.fixture
def thread(db):
    return ThreadModel.objects.create(text="Test Thread")

@pytest.fixture
def authenticated_page(page, live_server, user):
    # Login
    page.goto(live_server.url + reverse('login'))
    page.fill("input[name='username']", user.username)
    page.fill("input[name='password']", "testpass")
    page.click("button[type='submit']")
    return page

def login_user(page, live_server, username, password):
    page.goto(live_server.url + reverse('login'))
    page.fill("input[name='username']", username)
    page.fill("input[name='password']", password)
    page.click("button[type='submit']")

def logout_user(page, live_server):
    page.goto(live_server.url + reverse('logout'))

@pytest.mark.django_db
def test_upvote_and_cancel(authenticated_page, live_server, thread):
    authenticated_page.goto(live_server.url)
    authenticated_page.wait_for_selector(f"[data-id='{thread.pk}']", state="visible", timeout=5000)
    initial_score = int(authenticated_page.locator(f"[data-id='{thread.pk}'] .score").inner_text())
    base_class_upvote = "upVote p-1 rounded-full hover:bg-gray-100 transition-colors duration-200"
    base_class_downvote = "downVote p-1 rounded-full hover:bg-gray-100 transition-colors duration-200"

    # Upvote
    authenticated_page.click(f"[data-id='{thread.pk}'] .upVote")
    authenticated_page.wait_for_selector(f"[data-id='{thread.pk}'] .score:text-is('{initial_score + 1}')")
    expect(authenticated_page.locator(f"[data-id='{thread.pk}'] .upVote")).to_have_class(f"{base_class_upvote} voted text-blue-500")
    expect(authenticated_page.locator(f"[data-id='{thread.pk}'] .downVote")).to_have_class(f"{base_class_downvote} text-gray-500")
    
    # Cancel upvote
    authenticated_page.click(f"[data-id='{thread.pk}'] .upVote")
    authenticated_page.wait_for_selector(f"[data-id='{thread.pk}'] .score:text-is('{initial_score}')")
    expect(authenticated_page.locator(f"[data-id='{thread.pk}'] .upVote")).to_have_class(f"{base_class_upvote} text-gray-500")
    expect(authenticated_page.locator(f"[data-id='{thread.pk}'] .downVote")).to_have_class(f"{base_class_downvote} text-gray-500")

@pytest.mark.django_db
def test_upvote_then_downvote(authenticated_page, live_server, thread):
    authenticated_page.goto(live_server.url)
    authenticated_page.wait_for_selector(f"[data-id='{thread.pk}']", state="visible", timeout=5000)
    initial_score = int(authenticated_page.locator(f"[data-id='{thread.pk}'] .score").inner_text())
    base_class_upvote = "upVote p-1 rounded-full hover:bg-gray-100 transition-colors duration-200"
    base_class_downvote = "downVote p-1 rounded-full hover:bg-gray-100 transition-colors duration-200"
    
    # Upvote
    authenticated_page.click(f"[data-id='{thread.pk}'] .upVote")
    authenticated_page.wait_for_selector(f"[data-id='{thread.pk}'] .score:text-is('{initial_score + 1}')")
    expect(authenticated_page.locator(f"[data-id='{thread.pk}'] .upVote")).to_have_class(f"{base_class_upvote} voted text-blue-500")
    expect(authenticated_page.locator(f"[data-id='{thread.pk}'] .downVote")).to_have_class(f"{base_class_downvote} text-gray-500")
    
    # Downvote
    authenticated_page.click(f"[data-id='{thread.pk}'] .downVote")
    authenticated_page.wait_for_selector(f"[data-id='{thread.pk}'] .score:text-is('{initial_score - 1}')")
    expect(authenticated_page.locator(f"[data-id='{thread.pk}'] .downVote")).to_have_class(f"{base_class_downvote} voted text-red-500")
    expect(authenticated_page.locator(f"[data-id='{thread.pk}'] .upVote")).to_have_class(f"{base_class_upvote} text-gray-500")

@pytest.mark.django_db
def test_multiple_users_voting_same_thread(page, live_server, thread, user, user2, user3):
    base_class_upvote = "upVote p-1 rounded-full hover:bg-gray-100 transition-colors duration-200"
    base_class_downvote = "downVote p-1 rounded-full hover:bg-gray-100 transition-colors duration-200"

    # User 1 votes up
    login_user(page, live_server, user.username, "testpass")
    page.goto(live_server.url)
    page.wait_for_selector(f"[data-id='{thread.pk}']", state="visible", timeout=5000)
    initial_score = int(page.locator(f"[data-id='{thread.pk}'] .score").inner_text())
    page.click(f"[data-id='{thread.pk}'] .upVote")
    page.wait_for_selector(f"[data-id='{thread.pk}'] .score:text-is('{initial_score + 1}')")
    expect(page.locator(f"[data-id='{thread.pk}'] .upVote")).to_have_class(f"{base_class_upvote} voted text-blue-500")
    logout_user(page, live_server)

    # User 2 votes up
    login_user(page, live_server, user2.username, "testpass2")
    page.goto(live_server.url)
    page.wait_for_selector(f"[data-id='{thread.pk}']", state="visible", timeout=5000)
    current_score = int(page.locator(f"[data-id='{thread.pk}'] .score").inner_text())
    page.click(f"[data-id='{thread.pk}'] .upVote")
    page.wait_for_selector(f"[data-id='{thread.pk}'] .score:text-is('{current_score + 1}')")
    expect(page.locator(f"[data-id='{thread.pk}'] .upVote")).to_have_class(f"{base_class_upvote} voted text-blue-500")
    logout_user(page, live_server)

    # User 3 votes down
    login_user(page, live_server, user3.username, "testpass3")
    page.goto(live_server.url)
    page.wait_for_selector(f"[data-id='{thread.pk}']", state="visible", timeout=5000)
    current_score = int(page.locator(f"[data-id='{thread.pk}'] .score").inner_text())
    page.click(f"[data-id='{thread.pk}'] .downVote")
    page.wait_for_selector(f"[data-id='{thread.pk}'] .score:text-is('{current_score - 1}')")
    expect(page.locator(f"[data-id='{thread.pk}'] .downVote")).to_have_class(f"{base_class_downvote} voted text-red-500")
    
    # Final check
    final_score = int(page.locator(f"[data-id='{thread.pk}'] .score").inner_text())
    assert final_score == initial_score + 1, f"Expected score to be {initial_score + 1}, but got {final_score}"

@pytest.mark.django_db
def test_single_user_voting_multiple_threads(authenticated_page, live_server, db):
    base_class_upvote = "upVote p-1 rounded-full hover:bg-gray-100 transition-colors duration-200"
    base_class_downvote = "downVote p-1 rounded-full hover:bg-gray-100 transition-colors duration-200"

    # Create multiple threads
    thread1 = ThreadModel.objects.create(text="Test Thread 1")
    thread2 = ThreadModel.objects.create(text="Test Thread 2")
    thread3 = ThreadModel.objects.create(text="Test Thread 3")

    authenticated_page.goto(live_server.url)
    authenticated_page.wait_for_selector("[data-id]", state="visible", timeout=5000)

    # Vote on thread 1 (upvote)
    authenticated_page.click(f"[data-id='{thread1.pk}'] .upVote")
    authenticated_page.wait_for_selector(f"[data-id='{thread1.pk}'] .score:text-is('1')")
    expect(authenticated_page.locator(f"[data-id='{thread1.pk}'] .upVote")).to_have_class(f"{base_class_upvote} voted text-blue-500")

    # Vote on thread 2 (downvote)
    authenticated_page.click(f"[data-id='{thread2.pk}'] .downVote")
    authenticated_page.wait_for_selector(f"[data-id='{thread2.pk}'] .score:text-is('-1')")
    expect(authenticated_page.locator(f"[data-id='{thread2.pk}'] .downVote")).to_have_class(f"{base_class_downvote} voted text-red-500")

    # Vote on thread 3 (upvote then downvote)
    authenticated_page.click(f"[data-id='{thread3.pk}'] .upVote")
    authenticated_page.wait_for_selector(f"[data-id='{thread3.pk}'] .score:text-is('1')")
    authenticated_page.click(f"[data-id='{thread3.pk}'] .downVote")
    authenticated_page.wait_for_selector(f"[data-id='{thread3.pk}'] .score:text-is('-1')")
    expect(authenticated_page.locator(f"[data-id='{thread3.pk}'] .downVote")).to_have_class(f"{base_class_downvote} voted text-red-500")
    expect(authenticated_page.locator(f"[data-id='{thread3.pk}'] .upVote")).to_have_class(f"{base_class_upvote} text-gray-500")

    # Final check
    expect(authenticated_page.locator(f"[data-id='{thread1.pk}'] .score")).to_have_text("1")
    expect(authenticated_page.locator(f"[data-id='{thread2.pk}'] .score")).to_have_text("-1")
    expect(authenticated_page.locator(f"[data-id='{thread3.pk}'] .score")).to_have_text("-1")


    