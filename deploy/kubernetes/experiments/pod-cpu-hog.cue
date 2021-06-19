apiVersion: "litmuschaos.io/v1alpha1"
kind:       "ChaosEngine"
metadata: {
	name:      "carts-db-chaos"
	namespace: "sock-shop"
}
spec: {
	annotationCheck: "false"
	engineState:     "active"
	monitoring:      true
	appinfo: {
		appns: "sock-shop"
		// FYI, To see app label, apply kubectl get pods --show-labels
		// unique-label of the application under test (AUT)
		applabel: "name=carts-db"
		appkind:  "deployment"
	}
	chaosServiceAccount: "sock-shop-chaos-engine"
	jobCleanUpPolicy:    "delete"
	experiments: [ for i in [1, 2, 3, 4, 5] {
		name: "pod-cpu-hog"
		spec: components: env: [{
			name:  "TARGET_CONTAINER"
			value: "carts-db"
		}, {
			name:  "CPU_CORES"
			value: "2"
		}, {
			name:  "TOTAL_CHAOS_DURATION"
			value: "60"
		}, {
			name: "CHAOS_INTERVAL"
			value: "180"
		}]
	},]
}
