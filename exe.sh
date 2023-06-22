docker run \
--device=/dev/video0:/dev/video0 \
--ipc=host \
--ulimit memlock=-1 \
-it \
--rm \
--net=host \
--gpus all \
-e DISPLAY=$DISPLAY \
-v /tmp/.X11-unix/:/tmp/.X11-unix  \
$containers_name \
