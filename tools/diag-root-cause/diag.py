#!/usr/bin/env python3

import argparse
import json
import os
import re
import sys
from itertools import combinations

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import pcalg
from IPython.display import Image

from citest.fisher_z import ci_test_fisher_z

SIGNIFICANCE_LEVEL = 0.05

TARGET_DATA = {
    "containers": [],  # all
    "services": ["throughput", "latency"],
    "nodes": [
        "node_cpu_seconds_total",
        "node_disk_io_now",
        "node_filesystem_avail_bytes",
        "node_memory_MemAvailable_bytes",
        "node_network_receive_bytes_total",
        "node_network_transmit_bytes_total"
    ],
    # "middlewares": "all"}
}

CONTAINER_CALL_GRAPH = {
    "front-end": ["orders", "carts", "user", "catalogue"],
    "catalogue": ["front-end", "catalogue-db"],
    "catalogue-db": ["catalogue"],
    "orders": ["front-end", "orders-db", "carts", "user", "payement", "shipping"],
    "orders-db": ["orders"],
    "user": ["front-end", "user-db", "orders"],
    "user-db": ["user"],
    "payment": ["orders"],
    "shipping": ["orders", "rabbitmq"],
    "queue-master": ["rabbitmq"],
    "rabbitmq": ["shipping", "queue-master"],
    "carts": ["front-end", "carts-db", "orders"],
    "carts-db": ["carts"],
    "session-db": ["front-end"]
}

SERVICE_CONTAINERS = {
    "carts": ["carts", "carts-db"],
    "payment": ["payment"],
    "shipping": ["shipping"],
    "front-end": ["front-end"],
    "user": ["user", "user-db"],
    "catalogue": ["catalogue", "catalogue-db"],
    "orders": ["orders", "orders-db"]
}

ROOT_METRIC_NODE = "s-front-end_latency"


def read_data_file(tsdr_result_file):
    tsdr_result = json.load(open(tsdr_result_file))
    reduced_df = pd.DataFrame.from_dict(
        tsdr_result['reduced_metrics_raw_data'])

    # Filter by specified target metrics
    if 'containers' in TARGET_DATA:
        metrics = TARGET_DATA['containers']
        containers_df = reduced_df.filter(
            regex=f"^c-.+({'|'.join(metrics)})$")
    if 'services' in TARGET_DATA:
        metrics = TARGET_DATA['services']
        services_df = reduced_df.filter(
            regex=f"^s-.+({'|'.join(metrics)})$")
    if 'nodes' in TARGET_DATA:
        metrics = TARGET_DATA['nodes']
        nodes_df = reduced_df.filter(
            regex=f"^n-.+({'|'.join(metrics)})$")
    if 'middlewares' in TARGET_DATA:
        metrics = TARGET_DATA['middlewares']
        middlewares_df = reduced_df.filter(
            regex=f"^m-.+({'|'.join(metrics)})$")

    df = pd.concat([containers_df, services_df, nodes_df], axis=1)
    return df, tsdr_result['metrics_dimension'], \
        tsdr_result['clustering_info'], tsdr_result['components_mappings']


def build_no_paths(labels, mappings):
    containers_list, services_list, nodes_list = [], [], []
    for v in labels.values():
        if re.match("^c-", v):
            container_name = v.split("_")[0].replace("c-", "")
            if container_name not in containers_list:
                containers_list.append(container_name)
        elif re.match("^s-", v):
            service_name = v.split("_")[0].replace("s-", "")
            if service_name not in services_list:
                services_list.append(service_name)
        elif re.match("^n-", v):
            node_name = v.split("_")[0].replace("n-", "")
            if node_name not in nodes_list:
                nodes_list.append(node_name)

    containers_metrics = {}
    for c in containers_list:
        nodes = []
        for k, v in labels.items():
            if re.match("^c-{}_".format(c), v):
                nodes.append(k)
        containers_metrics[c] = nodes

    services_metrics = {}
    for s in services_list:
        nodes = []
        for k, v in labels.items():
            if re.match("^s-{}_".format(s), v):
                nodes.append(k)
        services_metrics[s] = nodes

    nodes_metrics = {}
    for n in nodes_list:
        nodes = []
        for k, v in labels.items():
            if re.match("^n-{}_".format(n), v):
                nodes.append(k)
        nodes_metrics[n] = nodes

    # Share host
    nodes_containers = {}
    for node, containers in mappings["nodes-containers"].items():
        for container in containers:
            if container == "nsenter":
                continue
            nodes_containers[container] = node.replace(
                "gke-microservices-experi-default-pool-", "")

    # C-C
    no_paths = []
    no_deps_C_C_pair = []
    for i, j in combinations(containers_list, 2):
        if j not in CONTAINER_CALL_GRAPH[i] and nodes_containers[i] != nodes_containers[j]:
            no_deps_C_C_pair.append([i, j])
    for pair in no_deps_C_C_pair:
        for i in containers_metrics[pair[0]]:
            for j in containers_metrics[pair[1]]:
                no_paths.append([i, j])
    print("No dependence C-C pairs: {}, No paths: {}".format(len(no_deps_C_C_pair), len(no_paths)))

    # S-S
    no_deps_S_S_pair = []
    for i, j in combinations(services_list, 2):
        has_comm = False
        for c1 in SERVICE_CONTAINERS[i]:
            for c2 in SERVICE_CONTAINERS[j]:
                if c2 in CONTAINER_CALL_GRAPH[c1]:
                    has_comm = True
        if not has_comm:
            no_deps_S_S_pair.append([i, j])
    for pair in no_deps_S_S_pair:
        for i in services_metrics[pair[0]]:
            for j in services_metrics[pair[1]]:
                no_paths.append([i, j])
    print("No dependence S-S pairs: {}, No paths: {}".format(len(no_deps_S_S_pair), len(no_paths)))

    # N-N
    no_deps_N_N_pair = []
    for i, j in combinations(nodes_list, 2):
        no_deps_N_N_pair.append([i, j])
        for n1 in nodes_metrics[i]:
            for n2 in nodes_metrics[j]:
                no_paths.append([n1, n2])
    print("No dependence N-N pairs: {}, No paths: {}".format(len(no_deps_N_N_pair), len(no_paths)))

    # C-N
    for node in nodes_list:
        for con, host_node in nodes_containers.items():
            if node != host_node:
                for n1 in nodes_metrics[node]:
                    if con not in containers_metrics:
                        continue
                    for c2 in containers_metrics[con]:
                        no_paths.append([n1, c2])
    print("[C-N] No paths: {}".format(len(no_paths)))

    # S-N
    for service in SERVICE_CONTAINERS:
        host_list = []
        for con in SERVICE_CONTAINERS[service]:
            if nodes_containers[con] not in host_list:
                host_list.append(nodes_containers[con])
        for node in nodes_list:
            if node not in host_list:
                if service not in services_metrics:
                    continue
                for s1 in services_metrics[service]:
                    for n2 in nodes_metrics[node]:
                        no_paths.append([s1, n2])
    print("[S-N] No paths: {}".format(len(no_paths)))

    # C-S
    for service in SERVICE_CONTAINERS:
        for con in containers_metrics:
            if con not in SERVICE_CONTAINERS[service]:
                if service not in services_metrics:
                    continue
                for s1 in services_metrics[service]:
                    for c2 in containers_metrics[con]:
                        no_paths.append([s1, c2])
    print("[C-S] No paths: {}".format(len(no_paths)))
    return no_paths


def prepare_init_graph(reduced_df, no_paths):
    dm = reduced_df.values
    print("Shape of data matrix: {}".format(dm.shape))
    init_g = nx.Graph()
    node_ids = range(len(reduced_df.columns))
    init_g.add_nodes_from(node_ids)
    for (i, j) in combinations(node_ids, 2):
        init_g.add_edge(i, j)
    print("Number of edges in complete graph : {}".format(init_g.number_of_edges()))
    for no_path in no_paths:
        init_g.remove_edge(no_path[0], no_path[1])
    print("Number of edges in init graph : {}".format(init_g.number_of_edges()))
    return init_g


def build_causal_graph(dm, labels, init_g, alpha, pc_stable):
    """
    Build causal graph with PC algorithm.
    """
    cm = np.corrcoef(dm.T)
    pc_method = 'stable' if pc_stable else None
    (G, sep_set) = pcalg.estimate_skeleton(indep_test_func=ci_test_fisher_z,
                                           data_matrix=dm,
                                           alpha=alpha,
                                           corr_matrix=cm,
                                           init_graph=init_g,
                                           method=pc_method)
    G = pcalg.estimate_cpdag(skel_graph=G, sep_set=sep_set)

    G = nx.relabel_nodes(G, labels)

    # Exclude nodes that have no path to "s-front-end_latency" for visualization
    remove_nodes = []
    undirected_G = G.to_undirected()
    for node in G.nodes():
        if not nx.has_path(undirected_G, node, ROOT_METRIC_NODE):
            remove_nodes.append(node)
            continue
        if re.match("^s-", node):
            color = "red"
        elif re.match("^c-", node):
            color = "blue"
        elif re.match("^m-", node):
            color = "purple"
        else:
            color = "green"
        G.nodes[node]["color"] = color
    G.remove_nodes_from(remove_nodes)
    print("Number of nodes: {}".format(G.number_of_nodes()))
    return G


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tsdr_resultfile", help="results file of tsdr")
    parser.add_argument("--citest-alpha",
                        default=SIGNIFICANCE_LEVEL,
                        type=int,
                        help="alpha value of independence test for building causality graph")
    parser.add_argument("--pc-stable",
                        action='store_true',
                        help='whether to use stable method of PC-algorithm')
    parser.add_argument("--out-dir",
                        help='output directory for saving graph image and metadata from tsdr')
    args = parser.parse_args()

    reduced_df, metrics_dimension, clustering_info, mappings = \
        read_data_file(args.tsdr_resultfile)
    if ROOT_METRIC_NODE not in reduced_df.columns:
        raise Exception(f"{args.tsdr_resultfile} has no root metric node: {ROOT_METRIC_NODE}")

    labels = {}
    for i in range(len(reduced_df.columns)):
        labels[i] = reduced_df.columns[i]
    print("--> Building no paths", file=sys.stderr)
    no_paths = build_no_paths(labels, mappings)
    print("--> Preparing initial graph", file=sys.stderr)
    init_g = prepare_init_graph(reduced_df, no_paths)
    print("--> Building causal graph", file=sys.stderr)
    g = build_causal_graph(
        reduced_df.values, labels, init_g, args.citest_alpha, args.pc_stable)

    agraph = nx.nx_agraph.to_agraph(g)
    img = agraph.draw(prog='sfdp', format='png')
    if args.out_dir is None:
        Image(img)
    else:
        id = os.path.splitext(os.path.basename(args.tsdr_resultfile))[0]
        imgfile = os.path.join(args.out_dir, id) + '.png'
        plt.savefig(imgfile)
        print(f"Saved the file of causal graph image to {imgfile}", file=sys.stderr)


if __name__ == '__main__':
    main()
