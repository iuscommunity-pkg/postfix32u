# Makefile for source rpm: postfix
# $Id$
NAME := postfix
SPECFILE = $(firstword $(wildcard *.spec))

include ../common/Makefile.common
