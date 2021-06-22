import "encoding/yaml"
import "encoding/json"
import "strings"

#chaosTypes: ["pod-cpu-hog", "pod-memory-hog", "pod-network-loss"]
#appLabels: ["user","user-db","shipping","carts","carts-db","orders","orders-db","catalogue","catalogue-db","payment","front-end"]

#container: {
	image: "lachlanevenson/k8s-kubectl"
	command: ["sh", "-c"]
	args: ["kubectl apply -f /tmp/chaosengine.yaml -n {{workflow.parameters.appNamespace}}; echo \"waiting {{workflow.parameters.chaosWaitSec}}s\"; sleep {{workflow.parameters.chaosWaitSec}}"]
}
#chaosTypeToExps: {
	"pod-cpu-hog": [{
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
	"pod-memory-hog": [{
		name: "pod-cpu-hog"
		spec: components: env: [{
			name:  "TARGET_CONTAINER"
			value: "{{inputs.parameters.appLabel}}"
		}, {
			name:  "MEMORY_CONSUMPTION"
			value: "500" // 500MB
		}, {
			name:  "TOTAL_CHAOS_DURATION"
			value: "{{workflow.parameters.chaosDurationSec}}"
		}]
	}]
	"pod-network-loss": [{
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
	}],
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
	}, {
		name: "gcsBucket"
		value: "microservices-demo-artifacts"
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
			name:     "get-metrics"
			template: "get-metrics-from-prometheus"
			arguments: parameters: [{
				name:  "jobN"
				value: "{{inputs.parameters.jobN}}"
			}, {
				name: "appLabel"
				value: "{{inputs.parameters.appLabel}}"
			}, {
				name: "chaosType"
				value: "\( type )"
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
		name: "get-metrics-from-prometheus"
		inputs: parameters: [{
			name: "jobN"
		}, {
			name: "appLabel"
		}, {
			name: "chaosType"
		}]
		container: {
			image: "ghcr.io/ai4sre/metrics-tools:latest"
			imagePullPolicy: "Always"
			args: [
				"--prometheus-url", "http://prometheus.monitoring.svc.cluster.local:9090",
				"--grafana-url", "http://grafana.monitoring.svc.cluster.local:3000",
				"--out", "/tmp/metrics.json",
			]
		}
		outputs: artifacts: [{
			name: "metrics-artifacts"
			path: "/tmp/metrics.json"
			gcs: {
				bucket: "{{ workflow.parameters.gcsBucket }}"
				// see https://github.com/argoproj/argo-workflows/blob/510b4a816dbb2d33f37510db1fd92b841c4d14d3/docs/workflow-controller-configmap.yaml#L93-L106
				key: """
				metrics/{{ workflow.creationTimestamp.Y }}/{{ workflow.creationTimestamp.m }}/{{ workflow.creationTimestamp.d }}/{{ workflow.name }}/{{ inputs.parameters.appLabel }}_{{ inputs.parameters.chaosType }}_{{ inputs.parameters.jobN }}.gz
				"""
			}
		}]
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
	}, for type, exps in #chaosTypeToExps {
		name: "run-chaos-\( type )"
		inputs: {
			parameters: [{
				name: "jobN"
			}, {
				name: "appLabel"
			}]
			artifacts: [{
				name: "run-chaos-\( type )"
				path: "/tmp/chaosengine.yaml"
				raw: data: yaml.Marshal(_cue_chaos_engine)
				_cue_chaos_engine: {
					apiVersion: "litmuschaos.io/v1alpha1"
					kind: "ChaosEngine"
					metadata: {
						name: "{{inputs.parameters.appLabel}}-chaos-{{inputs.parameters.jobN}}"
						namespace: "{{workflow.parameters.appNamespace}}"
					}
					spec: {
						annotationCheck: "false"
						engineState:     "active"
						monitoring:      true
						appinfo: {
							appns: "{{workflow.parameters.appNamespace}}"
							applabel: "name={{inputs.parameters.appLabel}}"
							appkind:  "deployment"
						}
						chaosServiceAccount: "{{workflow.parameters.chaosServiceAccount}}"
						jobCleanUpPolicy:    "delete"
						experiments: exps
					}
				}
			}]
		}
		container: #container
	}]
}
