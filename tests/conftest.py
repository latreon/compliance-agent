"""Shared fixtures: sample projects with known AI patterns."""

from pathlib import Path

import pytest

OPENAI_APP = """\
import logging
import openai

logger = logging.getLogger(__name__)
client = openai.OpenAI()

def ask(prompt: str) -> str:
    logger.info("calling model")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content
"""

ANTHROPIC_AGENT_APP = """\
import anthropic

client = anthropic.Anthropic()

def run_agent(user_input: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        tools=[{"name": "search", "description": "search the web"}],
        messages=[{"role": "user", "content": user_input}],
    )
    return response.content
"""

HIRING_APP = '''\
import openai

def screen_resume(resume_text: str) -> float:
    """Resume screening for recruitment: rank each job applicant."""
    client = openai.OpenAI()
    result = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"Score this candidate: {resume_text}"}],
    )
    return float(result.choices[0].message.content)
'''

PLAIN_UTILITY = """\
def add(a: int, b: int) -> int:
    return a + b
"""


def _write(base: Path, relative: str, content: str) -> Path:
    target = base / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


@pytest.fixture
def openai_project(tmp_path: Path) -> Path:
    """Project using OpenAI with logging present."""
    _write(tmp_path, "app.py", OPENAI_APP)
    _write(tmp_path, "README.md", "# Sample OpenAI app\n")
    return tmp_path


@pytest.fixture
def agent_project(tmp_path: Path) -> Path:
    """Project using Anthropic with tool-calling and no logging."""
    _write(tmp_path, "agent.py", ANTHROPIC_AGENT_APP)
    return tmp_path


@pytest.fixture
def hiring_project(tmp_path: Path) -> Path:
    """Project in an Annex III high-risk domain (employment/recruitment)."""
    _write(tmp_path, "resume_screening.py", HIRING_APP)
    return tmp_path


@pytest.fixture
def clean_project(tmp_path: Path) -> Path:
    """Project with no AI usage at all."""
    _write(tmp_path, "utils.py", PLAIN_UTILITY)
    return tmp_path
