times-%.out: travs-%
	python3 bbotime.py --dir travs-$* --simclocked >$@

outs: \
  times-2020-07-31.out \
  times-2020-08-04.out \
  times-2020-08-07.out \
  times-2020-08-11.out \
  times-2020-08-14.out \

