ARGO_MANIFEST_CUE=argowf-chaos.cue
CUE_EXPORT=cue eval --out yaml $(ARGO_MANIFEST_CUE)
ARGO_ANLYS_MANIFEST_CUE=argowf-analytics.cue
CUE_ANLYS_EXPORT=cue eval --out yaml $(ARGO_ANLYS_MANIFEST_CUE)
ARGO_NAMESPACE=litmus
ARGO_SUBMIT=argo submit -n $(ARGO_NAMESPACE)
ARGO_LATEST_DELETE=argo delete -n $(ARGO_NAMESPACE) @latest

.PHONY: run
run: lint
	$(CUE_EXPORT) | $(ARGO_SUBMIT) --watch -
	echo "If you cleanup your experiment, run 'argo delete @latest'"

# for checking the manifest of argo workflow
.PHONY: run-trial
run-trial: lint
	$(CUE_EXPORT) | $(ARGO_SUBMIT) --watch - --parameter-file argowf-trial.params.yaml || exit 1
	$(ARGO_LATEST_DELETE)

.PHONY: run-only-anomaly
run-only-anomaly: lint
	$(CUE_EXPORT) | $(ARGO_SUBMIT) --watch - --parameter-file argowf-only-anomaly.params.yaml || exit 1

.PHONY: print-yaml
print-yaml:
	$(CUE_EXPORT)

.PHONY: lint
lint:
	@$(CUE_EXPORT) | argo lint --strict -

.PHONY: anlys/run
anlys/run: anlys/lint
	$(CUE_ANLYS_EXPORT) | $(ARGO_SUBMIT) --watch -
	echo "If you cleanup your experiment, run 'argo delete @latest'"

.PHONY: anlys/lint
anlys/lint:
	$(CUE_ANLYS_EXPORT) | argo lint --strict -

.PHONY: logs-latest
logs-latest:
	argo logs -n $(ARGO_NAMESPACE) -f @latest

.PHONY: delete-latest
delete-latest:
	$(ARGO_LATEST_DELETE)
