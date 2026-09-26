"""Count physical source lines, excluding blank and comment-only lines."""
import io
from pathlib import PurePosixPath
import re
import tokenize

SUFFIXES = {'.py', '.pyi', '.sh', '.bash', '.zsh', '.rs', '.js', '.jsx',
            '.ts', '.tsx', '.c', '.h', '.cpp', '.hpp', '.go', '.java', '.swift'}


def is_source(path):
    return PurePosixPath(path).suffix in SUFFIXES or path in {
        '.githooks/pre-commit', '.githooks/pre-push'}


def count_source(path, data):
    text = data.decode('utf-8')
    if PurePosixPath(path).suffix in {'.py', '.pyi'}:
        used = set()
        ignored = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                   tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type not in ignored:
                used.update(range(token.start[0], token.end[0] + 1))
        lines = text.splitlines()
        return sum(bool(lines[n - 1].strip()) for n in used if n <= len(lines))
    shell = PurePosixPath(path).suffix in {'.sh', '.bash', '.zsh'} or path.startswith('.githooks/')
    strings = r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`'''
    comments = r'\#[^\n]*' if shell else r'//[^\n]*|/\*[\s\S]*?\*/'
    def strip(match):
        value = match.group()
        if value.startswith(('#', '//', '/*')):
            return '\n' * value.count('\n')
        return value
    cleaned = re.sub(strings + '|' + comments, strip, text)
    return sum(bool(line.strip()) for line in cleaned.splitlines())
