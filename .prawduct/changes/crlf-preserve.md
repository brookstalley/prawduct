---
schema: 1
type: fix
scope: crlf-preserve
date: 2026-10-28
title: The change-record commands keep a CRLF file CRLF when they rewrite it
closes: [brookstalley/prawduct#1073]
---

#1073. `core.write_all_or_none` writes exactly the text it is given (`newline=""`). Its callers
that rewrite a file built that text from a universal-newline `read_text`, so a CRLF file came out
LF: a whole-file diff. This happened on every platform. Before #733 the platform's default newline
hid it on Windows only.

- `core.read_text_and_eol` reads a file newline-preserving. It returns the text as parsers already
  saw it (`\n` only) together with the first line's ending. `core.with_eol` puts that ending back
  on the composed text. The parsers downstream are unchanged, so CRLF input parses exactly as
  before.
- `change_log_archive.bucket_write` is now the one reader of an archive month file that is about
  to be rewritten. `archive-change-log` and `cut-change-log` both go through it. The cut had its
  own copy of the read, and the issue did not name it.
- `archive-change-log` writes the live log back in its own ending. A new month file takes the live
  log's ending, since its entries moved from there.
- `migrate-change-log` writes `change-log.md` back in its own ending. The fragments it creates take
  that ending too.
- `plan new` needs no change. It creates only new files and rewrites none.
- A file with mixed endings is rewritten in its first line's ending.

## Consumer note
In a repo whose `.prawduct/` files use CRLF line endings, `archive-change-log`, `cut-change-log`
and `migrate-change-log` now keep CRLF in the files they rewrite. Before, they converted those
files to LF, and the diff showed every line as changed.
