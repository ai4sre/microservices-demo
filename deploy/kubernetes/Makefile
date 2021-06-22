ARGO_MANIFEST_CUE=experiments/argowf.cue
CUE_EXPORT=cue eval --out yaml $(ARGO_MANIFEST_CUE)
ARGO_SUBMIT=argo submit -n sock-shop

.PHONY: exp/run
exp/run: exp/lint
	$(CUE_EXPORT) | $(ARGO_SUBMIT) --watch -
	echo "If you cleanup your experiment, run 'argo delete @latest'"

# for checking the manifest of argo workflow
.PHONY: exp/run-trial
exp/run-trial: exp/lint
	$(CUE_EXPORT) | $(ARGO_SUBMIT) --watch - --parameter-file experiments/argowf-trial.params.yaml || exit 1
	argo delete @latest

.PHONY: exp/print-yaml
exp/print-yaml:
	$(CUE_EXPORT)

.PHONY: exp/lint
exp/lint:
	@$(CUE_EXPORT) | argo lint --strict --all-kinds -
