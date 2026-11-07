"""Offline Public Suffix List matching (ICANN and private sections).

Replaces tldextract. The bundled list (data/public_suffix_list.dat, MPL-2.0) is
read once at import; nothing is downloaded at runtime. Like tldextract with
include_psl_private_domains=True, an unlisted top-level label yields an empty
suffix instead of applying the implicit "*" rule.
"""
from dataclasses import dataclass
from pathlib import Path

import idna

LIST_PATH = Path(__file__).resolve().with_name("data") / "public_suffix_list.dat"


def _load(path=LIST_PATH):
    rules, wildcards, exceptions, private = set(), set(), set(), set()
    in_private = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if "===BEGIN PRIVATE DOMAINS===" in line:
            in_private = True
        rule = line.strip().split(" ")[0]
        if not rule or rule.startswith("//"):
            continue
        try:
            rule = ".".join(
                part if part == "*" else idna.encode(part, uts46=True).decode("ascii")
                for part in rule.lstrip("!").split(".")
            ) if not rule.startswith("!") else "!" + ".".join(
                idna.encode(part, uts46=True).decode("ascii") for part in rule[1:].split(".")
            )
        except idna.IDNAError:
            continue
        if in_private:
            private.add(rule.lstrip("!").removeprefix("*."))
        if rule.startswith("!"):
            exceptions.add(rule[1:])
        elif rule.startswith("*."):
            wildcards.add(rule[2:])
        else:
            rules.add(rule)
    return frozenset(rules), frozenset(wildcards), frozenset(exceptions), frozenset(private)


RULES, WILDCARDS, EXCEPTIONS, PRIVATE = _load()


@dataclass(frozen=True)
class Parts:
    subdomain: str
    domain: str
    suffix: str

    @property
    def private_suffix(self):
        """True when the suffix comes from the PSL private section (a shared hosting or
        platform namespace such as web.app or github.io): the registrable label is then
        a tenant name chosen by whoever registered it."""
        return bool(self.suffix) and self.suffix in PRIVATE

    @property
    def top_domain_under_public_suffix(self):
        return f"{self.domain}.{self.suffix}" if self.domain and self.suffix else ""

    registered_domain = top_domain_under_public_suffix


def public_suffix(hostname):
    """Return the longest matching public suffix of an ASCII hostname, or ''."""
    labels = hostname.lower().strip(".").split(".")
    best = ""
    for i in range(len(labels)):
        candidate = ".".join(labels[i:])
        parent = ".".join(labels[i + 1:])
        if candidate in EXCEPTIONS:
            # An exception rule makes the parent the suffix.
            return parent
        if candidate in RULES or (parent and parent in WILDCARDS):
            if len(candidate) > len(best):
                best = candidate
    return best


def split(hostname):
    hostname = hostname.lower().strip(".")
    suffix = public_suffix(hostname)
    if suffix == hostname:
        return Parts("", "", suffix)
    if not suffix:
        # Same shape as tldextract: last label as domain, no suffix.
        labels = hostname.split(".")
        return Parts(".".join(labels[:-1]), labels[-1], "")
    head = hostname[: -(len(suffix) + 1)].split(".")
    return Parts(".".join(head[:-1]), head[-1], suffix)


class Extractor:
    """Callable with the subset of the tldextract interface used by the app."""

    def __call__(self, hostname):
        return split(hostname)


PSL = Extractor()
