import hashlib
import logging
import os
from pathlib import Path
import subprocess
import typing

LOGGER = logging.getLogger(__name__)
VERBOSE_MARKER = "# ------------------------ >8 ------------------------"

def clear_comments(content: str) -> str:
	"""Remove all comments from the commit message.

	Args:
		content: The content of the commit message.
	"""
	return "\n".join(l for l in content.split("\n") if not l.startswith("#"))

			
def clear_verbose_code(content: str) -> str:
	"""Remove the verbose code marker and all code below it.

	Args:
		content: The content of the commit message.
	Returns:
		The content without any lines after th verbose marker.
	"""
	parts = content.partition(VERBOSE_MARKER)
	return parts[0]


def get_cached_message(repository_root: typing.Optional[str]=None, branch: typing.Optional[str]=None) -> str:
	"""
	Get the cached message for the given repository root and branch.

	If not repository root and/or branch is provided it will be calculated from
	the current working directory using git.

	Args:
		repository_root: The absolute path to the repository root that this cache
		file is for.
		branch: The name of the branch the repository is checked out on.
	Returns:
		The contents of the last commit message that failed to commit on this repository and branch.
	"""
	repository_root = repository_root or get_repository_root()
	branch = branch or get_repository_branch()
	cache_file_path = get_cache_file_path(repository_root, branch)
	return get_content(cache_file_path)


def get_cache_file_path(repository_root: str, branch: str) -> str:
	"""
	Get the full path to the file to save the commit message.

	Args:
		repository_root: The absolute path to the repository root that this cache
		file is for.
		branch: The name of the branch the repository is checked out on.
	"""
	cache_dir = xdg_cache_home() / "precommit-message-preservation"
	hasher = hashlib.sha256()
	hasher.update(repository_root.encode("utf-8"))
	repo_dir = os.path.basename(repository_root) + "-" + hasher.hexdigest()[:8]
	cache_file_path = os.path.join(cache_dir, repo_dir, branch + ".txt")
	return cache_file_path


def get_content(filename: str) -> str:
	try:
		with open(filename, "r") as f:
			return f.read()
	except OSError:
		return ""


def get_repository_branch() -> str:
	"""Get the name of the current branch for the git repository."""
	try:
		return subprocess.check_output(["git", "branch", "--show-current"]).decode("utf-8").strip()
	except subprocess.CalledProcessError as e:
		LOGGER.warning("Failed to get the git branch: %s", e)
	return "unknown"


def get_repository_root() -> str:
	"""Get the fully qualified path of the root of the git repository.

	If we aren't running in a git repository just return the current working directory."""
	try:
		git_dir = subprocess.check_output(["git", "rev-parse", "--git-dir"]).decode("utf-8")
		return os.path.abspath(os.path.dirname(git_dir))
	except subprocess.CalledProcessError as e:
		LOGGER.warning("Failed to call git rev-parse: %s", e)
	return os.path.abspath(os.curdir)


def remove_message_cache(repository_root: str, branch: str) -> None:
	"""Removes any files previously saved for caching failed messages.

	Args:
		repository_root: The absolute path to the repository root that this cache
		file is for.
		branch: The name of the branch the repository is checked out on.
	"""
	message_cache = get_cache_file_path(repository_root, branch)
	if os.path.exists(message_cache):
		os.remove(message_cache)
		LOGGER.debug("Removed commit message cache file at %s", message_cache)


def save_commit_message(message: str,
		repository_root: typing.Optional[str]=None,
		branch: typing.Optional[str]=None) -> None:
	"""Get a previously cached commit message, if applicable.

	Args:
		message: The commit message to save.
		repository_root: The absolute path to the repository root that this cache
		file is for.
		branch: The name of the branch the repository is checked out on.
	"""
	repository_root = repository_root or get_repository_root()
	branch = branch or get_repository_branch()
	message_cache = get_cache_file_path(repository_root, branch)
	os.makedirs(os.path.dirname(message_cache), exist_ok=True)
	LOGGER.info(f"Saving your bad commit message to {message_cache}")
	LOGGER.info("This will be automatically used by git next commit")
	cleared_message = clear_verbose_code(message)
	cleared_message = clear_comments(cleared_message)
	with open(message_cache, "w") as f:
		f.write(cleared_message)

def xdg_cache_home() -> Path:
	home = Path(os.path.expandvars("$HOME"))
	return Path(os.environ.get("XDG_CACHE_HOME", home / ".cache"))

class MessagePreservation():
	"""A context manager that handles saving and removing commit messages."""
	def __init__(self, message: str):
		self.branch = get_repository_branch()
		self.message = message
		self.repository_root = get_repository_root()

	def __enter__(self):
		return self

	def __exit__(self, type_, value, traceback):
		if any([type_, value, traceback]):
			save_commit_message(self.message, self.repository_root, self.branch)
			LOGGER.info("Your original commit message:\n\n%s\n", self.message)
		else:
			remove_message_cache(self.repository_root, self.branch)
		return False
		
