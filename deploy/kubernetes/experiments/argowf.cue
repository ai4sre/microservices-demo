import "encoding/yaml"
import "encoding/json"
import "strings"

#chaosTypes: ["pod-cpu-hog", "pod-network-loss"]
#appLabels: ["user","user-db","shipping","carts","carts-db","orders","orders-db","catalogue","catalogue-db","payment","front-end"]

#container: {
	image: "lachlanevenson/k8s-kubectl"
	command: ["sh", "-c"]
	args: ["kubectl apply -f /tmp/chaosengine.yaml -n {{workflow.parameters.appNamespace}}; echo \"waiting {{workflow.parameters.chaosWaitSec}}s\"; sleep {{workflow.parameters.chaosWaitSec}}"]
}

apiVersion: "argoproj.io/v1alpha1"
kind:       "Workflow"
metadata: generateName: "argowf-chaos-"
spec: {
	entrypoint:         "argowf-chaos"
	serviceAccountName: "argo-chaos"
	arguments: parameters: [{
		name:  "appNamespace"
		value: "sock-shop"
	}, {
		name:  "adminModeNamespace"
		value: "litmus"
	}, {
		name:  "chaosServiceAccount"
		value: "sock-shop-chaos-engine"
	}, {
		name: "appLabels"
		value: json.Marshal(_cue_app_labels)
		_cue_app_labels: #appLabels
	}, {
		name:  "repeatNum"
		value: 3
	}, {
		name:  "chaosDurationSec"
		value: 60
	}, {
		name:  "chaosWaitSec" // should be larger than chaosDurationSec
		value: 100
	}, {
		name:  "chaosIntervalSec"
		value: 1800 // 30min
	}, {
		name: "chaosTypes"
		value: strings.Join(#chaosTypes, ",")
	}]
	parallelism: 1
	templates: [{
		name: "argowf-chaos"
		steps: [ [ for type in #chaosTypes {
			name:     "run-chaos-\( type )"
			template: "expand-chaos-\( type )"
			arguments: parameters: [{
				name:  "repeatNum"
				value: "{{workflow.parameters.repeatNum}}"
			}, {
				name:  "appLabel"
				value: "{{item}}"
			}]
			withParam: "{{workflow.parameters.appLabels}}"
		},] ]
	}, for type in #chaosTypes {
		name: "expand-chaos-\( type )"
		inputs: parameters: [{
			name: "repeatNum"
		}, {
			name: "appLabel"
		}]
		steps: [ [{
			name:     "expand-chaos-\( type )-step"
			template: "run-chaos-\( type )-with-sleep"
			arguments: parameters: [{
				name:  "jobN"
				value: "{{item}}"
			}, {
				name:  "appLabel"
				value: "{{inputs.parameters.appLabel}}"
			}]
			withSequence: count: "{{inputs.parameters.repeatNum}}"
		}],
		]
	}, for type in #chaosTypes {
		name: "run-chaos-\( type )-with-sleep"
		inputs: parameters: [{
			name: "jobN"
		}, {
			name: "appLabel"
		}]
		steps: [ [{
			name:     "run-chaos-\( type )-with-sleep-step"
			template: "run-chaos-\( type )"
			arguments: parameters: [{
				name:  "jobN"
				value: "{{inputs.parameters.jobN}}"
			}, {
				name:  "appLabel"
				value: "{{inputs.parameters.appLabel}}"
			}]
		}, {
			name:     "sleep"
			template: "sleep-n-sec"
			arguments: parameters: [{
				name:  "seconds"
				value: "{{workflow.parameters.chaosIntervalSec}}"
			}]
		}],
		]
	}, {
		name: "sleep-n-sec"
		inputs: parameters: [{
			name: "seconds"
		}]
		container: {
			image: "alpine:latest"
			command: ["sh", "-c"]
			args: ["echo sleeping for {{inputs.parameters.seconds}} seconds; sleep {{inputs.parameters.seconds}}; echo done"]
		}
	}, {
		name: "run-chaos-pod-cpu-hog"
		inputs: {
			parameters: [{
				name: "jobN"
			}, {
				name: "appLabel"
			}]
			artifacts: [{
				name: "run-chaos-pod-cpu-hog"
				path: "/tmp/chaosengine.yaml"
				raw: data: yaml.Marshal(_cue_chaos_engine)
				_cue_chaos_engine: {
					apiVersion: "litmuschaos.io/v1alpha1"
					kind: "ChaosEngine"
					metadata: "{{inputs.parameters.appLabel}}-chaos-{{inputs.parameters.jobN}}"
					namespace: "{{workflow.parameters.appNamespace}}"
					spec: {
						annotationCheck: "false"
						engineState:     "active"
						monitoring:      true
						appinfo: {
							appns: "sock-shop"
							appLabel: "name={{input.parameters.appLabel}}"
							appkind:  "deployment"
						}
						chaosServiceAccount: "{{workflow.parameters.chaosServiceAccount}}"
						jobCleanUpPolicy:    "delete"
						experiments: [{
							name: "pod-cpu-hog"
							spec: components: env: [{
								name:  "TARGET_CONTAINER"
								value: "{{inputs.parameters.appLabel}}"
							}, {
								name:  "CPU_CORES"
								value: "2"
							}, {
								name:  "TOTAL_CHAOS_DURATION"
								value: "{{workflow.parameters.chaosDurationSec}}"
							}]
						}]
					}
				}
			}]
		}
		container: #container
	}, {
		name: "run-chaos-pod-network-loss"
		inputs: {
			parameters: [{
				name: "jobN"
			}, {
				name: "appLabel"
			}]
			artifacts: [{
				name: "run-chaos-pod-network-loss"
				path: "/tmp/chaosengine.yaml"
				raw: data: yaml.Marshal(_cue_chaos_engine)
				_cue_chaos_engine: {
					apiVersion: "litmuschaos.io/v1alpha1"
					kind: "ChaosEngine"
					metadata: "{{inputs.parameters.appLabel}}-chaos-{{inputs.parameters.jobN}}"
					namespace: "{{workflow.parameters.appNamespace}}"
					spec: {
						annotationCheck: "false"
						engineState:     "active"
						monitoring:      true
						appinfo: {
							appns: "sock-shop"
							appLabel: "name={{input.parameters.appLabel}}"
							appkind:  "deployment"
						}
						chaosServiceAccount: "{{workflow.parameters.chaosServiceAccount}}"
						jobCleanUpPolicy:    "delete"
						experiments: [{
							name: "pod-network-loss"
							spec: components: env: [{
								name:  "TARGET_CONTAINER"
								value: "{{inputs.parameters.appLabel}}"
							}, {
								name:  "NETWORK_INTERFACE"
								value: "eth0"
							}, {
								name: "NETWORK_PACKET_LOSS_PERCENTAGE"
								value: "60"
							}, {
								name: "SOCKET_PATH"
								value: "/var/run/docker.sock"
							}, {
								name:  "TOTAL_CHAOS_DURATION"
								value: "{{workflow.parameters.chaosDurationSec}}"
							}]
						}]
					}
				}
			}]
		}
		container: #container
	}]
}
