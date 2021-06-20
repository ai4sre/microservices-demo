ARGO_MANIFEST_CUE=experiments/argowf.cue
CUE_EXPORT=cue eval --out yaml $(ARGO_MANIFEST_CUE)

.PHONY: exp/run
exp/run:
	$(CUE_EXPORT) | argo submit --watch -
	echo "If you cleanup your experiment, run 'argo delete @latest'"

.PHONY: exp/run-for-checking
exp/run-for-checking:
	$(CUE_EXPORT) | argo submit --watch - --parameter-file experiments/argowf-checking-params.yaml || exit 1
	argo delete @latest

.PHONY: exp/print-yaml
exp/print-yaml:
	$(CUE_EXPORT)
