#!/usr/bin/env bash
# Linux container only: audio formats used by Speech, with no XML, graphics or network.
set -euo pipefail
cd /build
python tools/fetch_audio_source.py
cd sources/ffmpeg-7.1.5
./configure --prefix=/build/audio --disable-everything --disable-autodetect \
  --disable-network --disable-doc --disable-debug --disable-x86asm \
  --disable-shared --enable-static --disable-programs --enable-ffmpeg \
  --enable-protocol=file,pipe --enable-demuxer=wav,mp3,flac,ogg,concat \
  --enable-muxer=wav,mp3 --enable-parser=mpegaudio,flac,vorbis,opus \
  --enable-decoder=pcm_u8,pcm_s16le,pcm_s16be,pcm_s24le,pcm_s24be,pcm_s32le,pcm_s32be,pcm_f32le,pcm_f64le,pcm_alaw,pcm_mulaw,mp3,mp3float,flac,vorbis,opus \
  --enable-encoder=pcm_s16le,libmp3lame --enable-libmp3lame \
  --enable-filter=aresample,aformat,anull,abuffer,abuffersink
make -j2
make install
mkdir -p /build/audio/licenses
cp COPYING.LGPLv2.1 LICENSE.md /build/audio/licenses/
cp /build/tools/native_audio_source.json /build/audio/licenses/source.json
./ffmpeg -buildconf > /build/audio/licenses/build-configuration.txt 2>&1
sha256sum /build/audio/bin/ffmpeg | cut -d ' ' -f1 > /build/audio/licenses/binary.sha256
