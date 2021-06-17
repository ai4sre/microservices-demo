apiVersion: "litmuschaos.io/v1alpha1"
kind:       "ChaosEngine"
metadata: {
	name:      "carts-db-chaos"
	namespace: "sock-shop"
}
spec: {
	// It can be true/false
	annotationCheck: "false"
	//ex. values: sock-shop:name=carts
	engineState: "active"
	// It can be delete/retain
	monitoring: true
	appinfo: {
		appns: "sock-shop"
		// FYI, To see app label, apply kubectl get pods --show-labels
		// unique-label of the application under test (AUT)
		applabel: "name=carts-db"
		appkind:  "deployment"
	}
	chaosServiceAccount: "sock-shop-chaos-engine"
	jobCleanUpPolicy:    "delete"
	experiments: [{
		name: "pod-network-loss"
		spec: components: env: [{
			//Network interface inside target container
			name:  "NETWORK_INTERFACE"
			value: "eth0"
		}, {
			name:  "NETWORK_PACKET_LOSS_PERCENTAGE"
			value: "80"
		}, {
			name:  "TOTAL_CHAOS_DURATION"
			value: "60"
		}, {
			// in seconds

			name:  "SOCKET_PATH"
			value: "/var/run/docker.sock"
		}]
	}]
}
