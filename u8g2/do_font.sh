#! /bin/bash -e
# Grab a u8g2 "C" font file from the github repo and produce a u8f and py file locally.
# usage: ./do_font.sh luRS18_te
# assumes the u8g2 github repo is located at ../../u8g2
font=$1
if [[ -z "$font" ]]; then
    echo "usage: $0 <font name>, example: $0 luRS19_te" 1>&2
    exit 1
fi
u8g2py=$(dirname $0)
u8g2fonts=$u8g2py/../../u8g2/tools/font/build/single_font_files
ffile=$u8g2fonts/u8g2_font_$font.c
if [[ ! -f $ffile ]]; then
    echo "Font file $ffile not found" 1>&2
    exit 1
fi
$u8g2py/u8g2_convert.py <$ffile
