
.PHONY: exp/run
exp/run:
	argo submit --watch experiments/argowf.yaml
	echo "If you cleanup your experiment, run 'argo delete @latest'"

.PHONY: exp/run-for-checking
exp/run-for-checking:
	argo submit --watch experiments/argowf.yaml --parameter-file experiments/argowf-checking-params.yaml
	argo delete @latest
