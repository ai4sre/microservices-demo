ARGO_MANIFEST_CUE=argowf.cue
CUE_EXPORT=cue eval --out yaml $(ARGO_MANIFEST_CUE)
ARGO_SUBMIT=argo submit -n sock-shop

.PHONY: run
run: lint
	$(CUE_EXPORT) | $(ARGO_SUBMIT) --watch -
	echo "If you cleanup your experiment, run 'argo delete @latest'"

# for checking the manifest of argo workflow
.PHONY: run-trial
run-trial: lint
	$(CUE_EXPORT) | $(ARGO_SUBMIT) --watch - --parameter-file argowf-trial.params.yaml || exit 1
	argo delete @latest

.PHONY: print-yaml
print-yaml:
	$(CUE_EXPORT)

.PHONY: lint
lint:
	@$(CUE_EXPORT) | argo lint --strict --all-kinds -
