import pytest

from ppt_templates.loader import find_repo_root, load_example

TEMPLATE_ID = "system.solution-layered-arch"


@pytest.fixture(scope="session")
def root():
    return find_repo_root()


@pytest.fixture
def deck(root):
    return {"style": "default", "pages": [{"template": TEMPLATE_ID, "data": load_example(root, TEMPLATE_ID)}]}
