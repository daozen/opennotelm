#!/usr/bin/env bash
# Linux container build only: preserve the locked lxml release and rebuild its libraries.
set -euo pipefail
cd /build
python tools/fetch_xml_sources.py --output /build/sources
xml_version=$(python -c 'import json; print(json.load(open("tools/native_xml_sources.json"))["libxml2"]["version"])')
xslt_version=$(python -c 'import json; print(json.load(open("tools/native_xml_sources.json"))["libxslt"]["version"])')
lxml_version=$(python -c 'import json; print(json.load(open("sources/sources.json"))["lxml"]["version"])')
cmake -S "sources/libxml2-$xml_version" -B /build/xml-build \
  -DCMAKE_INSTALL_PREFIX=/build/native -DCMAKE_INSTALL_LIBDIR=lib \
  -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=OFF -DLIBXML2_WITH_PYTHON=OFF -DLIBXML2_WITH_TESTS=OFF \
  -DLIBXML2_WITH_PROGRAMS=OFF -DLIBXML2_WITH_HTTP=OFF -DLIBXML2_WITH_ZLIB=OFF \
  -DLIBXML2_WITH_LEGACY=ON
cmake --build /build/xml-build --parallel 2
cmake --install /build/xml-build
(
  cd "sources/libxslt-$xslt_version"
  PKG_CONFIG_PATH=/build/native/lib/pkgconfig ./configure \
    --prefix=/build/native --disable-shared --enable-static --with-pic \
    --without-python --without-crypto --with-libxml-prefix=/build/native
  make -j2
  make install
)
mkdir -p /build/wheels /build/licenses
(
  cd "sources/lxml-$lxml_version"
  PKG_CONFIG_PATH=/build/native/lib/pkgconfig \
  LXML_STATIC_INCLUDE_DIRS=/build/native/include:/build/native/include/libxml2 \
  LXML_STATIC_LIBRARY_DIRS=/build/native/lib \
  LXML_STATIC_BINARIES=/build/native/lib/libexslt.a:/build/native/lib/libxslt.a:/build/native/lib/libxml2.a \
  CFLAGS='-O2 -g0' python setup.py bdist_wheel --static --without-cython --dist-dir /build/wheels
)
cp "sources/libxml2-$xml_version/Copyright" /build/licenses/libxml2-Copyright
cp "sources/libxslt-$xslt_version/Copyright" /build/licenses/libxslt-Copyright
cp sources/sources.json /build/licenses/sources.json
