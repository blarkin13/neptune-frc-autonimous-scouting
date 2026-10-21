#!/bin/sh
# Corresponding source: FFmpeg 9.0.2, LGPL; no optional GPL libraries.
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build_dir="$repo_dir/.helper-build/native/ffmpeg-build"
mkdir -p "$build_dir"
tar -xf "$repo_dir/.helper-build/vendor/ffmpeg-9.0.2.tar.xz" -C "$build_dir"
cd "$build_dir/ffmpeg-9.0.2"
./configure --prefix=/tmp/neptune-native-ffmpeg-unused --disable-everything --disable-autodetect --disable-network \
 --disable-shared --enable-static --disable-doc --disable-debug \
 --extra-cflags=-mmacosx-version-min=14.0 --extra-ldflags=-mmacosx-version-min=14.0 \
 --enable-ffmpeg --enable-ffprobe --enable-protocol=file,pipe \
 --enable-demuxer=mov,matroska,avi,flv,mpegts,image2,image2pipe,rawvideo \
 --enable-decoder=h264,hevc,vp9,vp8,av1,mjpeg,png,aac,opus,mp3 --enable-parser=h264,hevc,vp9,vp8,av1,aac \
 --enable-encoder=mjpeg,ppm,rawvideo --enable-muxer=image2,image2pipe,framemd5,rawvideo,mp4,mov,matroska \
 --enable-filter=scale,fps,crop,split,format,null,aresample,anull,setpts --enable-swscale
make -j4
