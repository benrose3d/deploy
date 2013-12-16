import os
import json
from urllib2 import urlopen, Request


def expand_path(path):
    return os.path.expanduser(os.path.expandvars(path))


def find_github_token():
    file_key = None
    key_path = expand_path("~/.github_token")

    if os.path.exists(key_path):
        with open(key_path) as fp:
            file_key = fp.read()

    keys = [
        os.environ.get("GITHUB_TOKEN"),
        file_key,
    ]

    try:
        return filter(None, keys)[0]
    except IndexError:
        raise IndexError("No GitHub token was found")


class SSHKey(object):

    def __init__(self, filename):
        self.file = filename

    def as_python(self):
        with open(expand_path(self.file), "r") as fp:
            data = fp.read().split()

        return { "title": data[-1], "key": " ".join(data[:2]) }

    @property
    def __eq__(self, other):
        return other == self.as_python()["key"]

    def as_json(self):
        return json.dumps(self.as_python())


class GitHubSSHKey(object):

    API_URL = "https://api.github.com/repos/{owner}/{repo}/keys"

    def __init__(self, token, owner="finiteloopsoftware"):
        self.token = token
        self.owner = owner

    def _make_request(self, data=None, **kwargs):
        return urlopen(Request(self.API_URL.format(**kwargs), data,
            { "Authorization": "token {0}".format(self.token) }))

    def add_key(self, key_file, repo):
        return self._make_request(
                SSHKey(key_file).as_json(), owner=self.owner, repo=repo)

    def key_in_repo(self, key_file, repo):
        response = self._make_request(owner=self.owner, repo=repo)
        our_key = SSHKey(key_file)
        return any([
            (k["key"] == our_key) for k in json.loads(response.read())
        ])
