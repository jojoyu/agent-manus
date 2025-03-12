#!/bin/bash
Xvfb :99 -screen 0 1024x768x16 & 
sleep 1
exec "$@"
