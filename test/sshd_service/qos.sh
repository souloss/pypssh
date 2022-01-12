#!/usr/bin/env sh
# TODO 动态生成随机故障
tc  qdisc  add  dev  ens192  root  netem  delay  100ms  10ms  30% loss 5%