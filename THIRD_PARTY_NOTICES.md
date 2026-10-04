# Third-party notices

[简体中文说明](docs/THIRD_PARTY_NOTICES.zh-CN.md)

The project's MIT license covers its own code. Dependencies and bundled components
retain their original terms. The pinned [dependency inventory](docs/DEPENDENCIES.json)
lists application packages and declared licenses, including transitive dependencies;
development/platform-only entries are not all shipped in a runtime image.

## Distribution of notices and sources

- Release assets contain original Python runtime and frontend production license/
  copyright texts, copied from installed packages without translating or replacing them.
- The frontend build keeps these texts in `frontend/dist/third-party/`; the image
  keeps Python notices under `/app/licenses/python/` and installed package metadata.
- PDFium and its native libraries have their own build notices retained alongside
  pypdfium2. Playwright's Node driver, Chromium, Debian packages and fonts retain
  their own notices in the image; Chromium additionally provides `chrome://credits`. The image preserves exported
  built-in credits/terms under `/app/licenses/browser/`, without external page access.
- Debian/Noto font notices remain under `/usr/share/doc/` and installed fonts.
  The Docker-specific rebuilt lxml library retains libxml2/libxslt/libexslt copyright
  texts and verified source hashes under `/app/licenses/native-xml/`; release assets
  include these unmodified native sources and notices too.
  The two pinned Debian security replacements retain complete package copyright and
  common license texts under `/app/licenses/debian-security/`. Release attachments
  include their verified original source archives, Debian packaging and notices;
  ACL retains LGPL-2.1-or-later, rather than inheriting the project's MIT license.
  Browser/OS/native dependencies are not covered completely by the application inventory;
  image releases separately create platform-specific SBOM/provenance.
- certifi uses MPL-2.0. tld offers MPL-1.1/GPL/LGPL alternatives; this distribution
  follows its MPL-1.1 option. Their files are unmodified; release assets include the
  exact upstream source distributions verified against `uv.lock` hashes. Source
  locations are also listed in the inventory. Do not remove these notices/source access.
- Icon geometry copied into native Deck rendering requires the Lucide notice below.

Upstream metadata alone is not a complete legal audit. Review changes before adding
dependencies, modifying copyleft files, redistributing model weights or bundling assets.
No model weights, user books, generated user Decks or provider credentials are distributed.
Public test/demo materials are synthetic; their rights are documented with the fixtures.

## Lucide pictograms

OpenNoteLM bundles selected Lucide v0.468.0 geometry for native Deck diagrams.
Source: the existing `lucide-react` dependency.

ISC License

Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of Feather (MIT). All other copyright (c) for Lucide are held by Lucide Contributors 2022.

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
