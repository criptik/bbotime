times-%.out: travs-%
	python3 bbotime.py --dir travs-$* --simclocked ${OPTS} >$@

all: times-$X.out

outs: \
  times-2020-07-31.out \
  times-2020-08-04.out \
  times-2020-08-07.out \
  times-2020-08-11.out \
  times-2020-08-14.out \

# note: 2020-08-21 should have --robotScores 68.25 43.65 
#   and 2020-08-25 should have --robotScores 58.73 46.83 
