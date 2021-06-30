import "encoding/yaml"
import "encoding/json"
import "strings"

#appLabels: ["user","user-db","shipping","carts","carts-db","orders","orders-db","catalogue","catalogue-db","payment","front-end"]

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
		name: "pod-memory-hog"
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
			name:  "TOTAL_CHAOS_DURATION"
			value: "{{workflow.parameters.chaosDurationSec}}"
		}]
	}]
	"pod-network-latency": [{
		name: "pod-network-latency"
		spec: components: env: [{
			name:  "TARGET_CONTAINER"
			value: "{{inputs.parameters.appLabel}}"
		}, {
			name:  "NETWORK_INTERFACE"
			value: "eth0"
		}, {
			name: "NETWORK_LATENCY"
			value: "2000"
		}, {
			name:  "TOTAL_CHAOS_DURATION"
			value: "{{workflow.parameters.chaosDurationSec}}"
		}]
	}]
	"pod-io-stress": [{
		name: "pod-io-stress"
		spec: components: env: [{
			name:  "TARGET_CONTAINER"
			value: "{{inputs.parameters.appLabel}}"
		}, {
			name:  "FILESYSTEM_UTILIZATION_PERCENTAGE"
			value: "50"
		}, {
			name:  "TOTAL_CHAOS_DURATION"
			value: "{{workflow.parameters.chaosDurationSec}}"
		}]
	}]
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
		value: "litmus-admin"
	}, {
		name: "appLabels"
		value: json.Marshal(_cue_app_labels)
		_cue_app_labels: #appLabels
	}, {
		name:  "repeatNum"
		value: 3
	}, {
		name:  "chaosDurationSec"
		value: 300
	}, {
		name:  "chaosIntervalSec"
		value: 1800 // 30min
	}, {
		name: "chaosTypes"
		value: strings.Join([for type, _ in #chaosTypeToExps { "'" + type + "'" }], ",")
	}, {
		name: "restartPod"
		value: 1
	}, {
		name: "gcsBucket"
		value: "microservices-demo-artifacts"
	}, {
		name: "litmusJobCleanupPolicy"
		value: "delete" // defaut value in litmus
	}]
	parallelism: 1
	templates: [{
		name: "argowf-chaos"
		steps: [ [ for type, _ in #chaosTypeToExps {
			name:     "run-chaos-\( type )"
			template: "repeat-chaos-\( type )"
			arguments: parameters: [{
				name:  "repeatNum"
				value: "{{workflow.parameters.repeatNum}}"
			}, {
				name:  "appLabel"
				value: "{{item}}"
			}]
			withParam: "{{workflow.parameters.appLabels}}"
			// append 'dummy' because of list in argo should be >=2
			// see https://github.com/argoproj/argo-workflows/issues/1633#issuecomment-645433742
			when: "'\( type )' in ({{workflow.parameters.chaosTypes}},'dummy')"
		},] ]
	}, for type, v in #chaosTypeToExps {
		name: "repeat-chaos-\( type )"
		inputs: parameters: [{
			name: "repeatNum"
		}, {
			name: "appLabel"
		}]
		steps: [ [{
			name:     "inject-chaos-\( type )-and-get-metrics"
			template: "inject-chaos-\( type )-and-get-metrics"
			arguments: parameters: [{
				name:  "jobN"
				value: "{{item}}"
			}, {
				name:  "appLabel"
				value: "{{inputs.parameters.appLabel}}"
			}]
			withSequence: count: "{{inputs.parameters.repeatNum}}"
		}, {
			name:     "sleep"
			template: "sleep-n-sec"
			arguments: parameters: [{
				name:  "seconds"
				value: "{{workflow.parameters.chaosIntervalSec}}"
			}]
		}] ]
	}, for type, _ in #chaosTypeToExps {
		#chaosEngineName: "{{inputs.parameters.appLabel}}-\( type )-{{inputs.parameters.jobN}}"
		name: "inject-chaos-\( type )-and-get-metrics"
		inputs: parameters: [{
			name: "jobN"
		}, {
			name: "appLabel"
		}]
		steps: [ [{
			name: "reset-chaosengine"
			template: "revert-chaosengine"
			arguments: parameters: [{
				name: "chaosEngineName"
				value: #chaosEngineName
			}]
		}],
		[{
			name:     "inject-chaos-\( type )"
			template: "inject-chaos-\( type )"
			arguments: parameters: [{
				name:  "chaosEngineName"
				value: #chaosEngineName
			}, {
				name:  "appLabel"
				value: "{{inputs.parameters.appLabel}}"
			}]
		}], [{
			name: "get-injection-finished-time"
			template: "get-injection-finished-time"
			arguments: parameters: [{
				name:  "chaosEngineName"
				value: #chaosEngineName
			}]
		}], [{
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
			}, {
				name: "endTimestamp"
				value: "{{steps.get-injection-finished-time.outputs.result}}"
			}]
		}], [{
			name: "restart-pod-injected-chaos"
			template: "restart-pod"
			arguments: parameters: [{
				name: "appLabel"
				value: "{{inputs.parameters.appLabel}}"
			}]
			when: "{{workflow.parameters.restartPod}} == 1"
		}], [{
			name: "revert-chaosengine"
			template: "revert-chaosengine"
			arguments: parameters: [{
				name:  "chaosEngineName"
				value: #chaosEngineName
			}]
		}],
		]
	}, {
		// return <injection started time> + <chaos duration>
		name: "get-injection-finished-time"
		inputs: parameters: [{
			name: "chaosEngineName"
		}]
		script: {
			image: "bitnami/kubectl"
			command: ["sh"]
			source: """
			ts=$(kubectl get chaosengine -n litmus -o=jsonpath='{.items[0].metadata.creationTimestamp}')
			expr $(date -d $ts +'%s') + {{workflow.parameters.chaosDurationSec}}
			"""
		}
	}, {
		name: "get-metrics-from-prometheus"
		inputs: parameters: [{
			name: "jobN"
		}, {
			name: "appLabel"
		}, {
			name: "chaosType"
		}, {
			name: "endTimestamp"
		}]
		container: {
			image: "ghcr.io/ai4sre/metrics-tools:latest"
			imagePullPolicy: "Always"
			args: [
				"--prometheus-url",
				"http://prometheus.monitoring.svc.cluster.local:9090",
				"--grafana-url",
				"http://grafana.monitoring.svc.cluster.local:3000",
				"--end",
				"{{inputs.parameters.endTimestamp}}",
				"--out",
				"/tmp/{{workflow.creationTimestamp.Y}}-{{workflow.creationTimestamp.m}}-{{workflow.creationTimestamp.d}}-{{workflow.name}}-{{inputs.parameters.appLabel}}_{{inputs.parameters.chaosType}}_{{inputs.parameters.jobN}}.json",
			]
		}
		outputs: artifacts: [{
			name: "metrics-artifacts"
			path: "/tmp/{{workflow.creationTimestamp.Y}}-{{workflow.creationTimestamp.m}}-{{workflow.creationTimestamp.d}}-{{workflow.name}}-{{inputs.parameters.appLabel}}_{{inputs.parameters.chaosType}}_{{inputs.parameters.jobN}}.json"
			gcs: {
				bucket: "{{ workflow.parameters.gcsBucket }}"
				// see https://github.com/argoproj/argo-workflows/blob/510b4a816dbb2d33f37510db1fd92b841c4d14d3/docs/workflow-controller-configmap.yaml#L93-L106
				key: """
				metrics/{{workflow.creationTimestamp.Y}}/{{workflow.creationTimestamp.m}}/{{workflow.creationTimestamp.d}}/{{workflow.name}}/{{inputs.parameters.appLabel}}_{{inputs.parameters.chaosType}}_{{inputs.parameters.jobN}}.json.tgz
				"""
			}
		}]
	}, {
		name: "restart-pod"
		inputs: parameters: [{
			name: "appLabel"
		}]
		container: {
			image: "bitnami/kubectl"
			command: ["sh", "-c"]
			args: ["kubectl rollout restart deployment/{{inputs.parameters.appLabel}} -n {{workflow.parameters.appNamespace}}; echo sleeping for 60 seconds; sleep 60; echo done"]
		}
	}, {
		name: "revert-chaosengine"
		inputs: parameters: [{
			name: "chaosEngineName"
		}]
		container: {
			image: "bitnami/kubectl"
        	command: ["sh", "-c"]
        	args: ["kubectl delete --wait chaosengine {{inputs.parameters.chaosEngineName}} -n {{workflow.parameters.adminModeNamespace}}; true"]
		}
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
		name: "inject-chaos-\( type )"
		inputs: {
			parameters: [{
				name: "chaosEngineName"
			}, {
				name: "appLabel"
			}]
			artifacts: [{
				name: "manifest-for-injecting-\(type)"
				path: "/tmp/chaosengine.yaml"
				raw: data: yaml.Marshal(_cue_chaos_engine)
				_cue_chaos_engine: {
					apiVersion: "litmuschaos.io/v1alpha1"
					kind: "ChaosEngine"
					metadata: {
						name: "{{inputs.parameters.chaosEngineName}}"
						namespace: "{{workflow.parameters.adminModeNamespace}}"
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
						jobCleanUpPolicy:    "{{workflow.parameters.litmusJobCleanupPolicy}}"
						experiments: exps
					}
				}
			}]
		}
		container: {
			image: "bitnami/kubectl"
			command: ["sh", "-c"]
			args: ["kubectl apply -f /tmp/chaosengine.yaml -n {{workflow.parameters.adminModeNamespace}}; echo \"waiting {{workflow.parameters.chaosDurationSec}}s\"; sleep {{workflow.parameters.chaosDurationSec}}"]
		}
	}]
}
