#!/usr/bin/env python3

import argparse
import json
import os
import random
import re
import sys
import time
from concurrent import futures
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist, squareform
from statsmodels.tsa.stattools import adfuller

from clustering.kshape import kshape
from clustering.metricsnamecluster import cluster_words
from clustering.sbd import sbd, silhouette_score
from util import util

TSIFTER_METHOD = 'tsifter'
SIEVE_METHOD = 'sieve'

PLOTS_NUM = 120
SIGNIFICANCE_LEVEL = 0.05
THRESHOLD_DIST = 0.01
TARGET_DATA = {"containers": "all",
               "services": "all",
               "middlewares": "all"}


def reduce_series_with_cv(data_df):
    reduced_by_cv_df = pd.DataFrame()
    for col in data_df.columns:
        data = data_df[col].values
        mean = data.mean()
        std = data.std()
        if mean == 0. and std == 0.:
            cv = 0
        else:
            cv = std / mean
        if cv > 0.002:
            reduced_by_cv_df[col] = data_df[col]
    return reduced_by_cv_df


def reduce_series_with_adf(data_df, max_workers):
    reduced_by_st_df = pd.DataFrame()
    with futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_col = {}
        for col in data_df.columns:
            data = data_df[col].values
            if data.sum() == 0. or len(np.unique(data)) == 1 or np.isnan(data.sum()):
                continue
            future_to_col[executor.submit(adfuller, data)] = col
        for future in futures.as_completed(future_to_col):
            col = future_to_col[future]
            p_val = future.result()[1]
            if not np.isnan(p_val):
                if p_val >= SIGNIFICANCE_LEVEL:
                    reduced_by_st_df[col] = data_df[col]
    return reduced_by_st_df


def hierarchical_clustering(target_df, dist_func):
    series = target_df.values.T
    norm_series = util.z_normalization(series)
    dist = pdist(norm_series, metric=dist_func)
    # distance_list.extend(dist)
    dist_matrix = squareform(dist)
    z = linkage(dist, method="single", metric=dist_func)
    labels = fcluster(z, t=THRESHOLD_DIST, criterion="distance")
    cluster_dict = {}
    for i, v in enumerate(labels):
        if v not in cluster_dict:
            cluster_dict[v] = [i]
        else:
            cluster_dict[v].append(i)
    clustering_info, remove_list = {}, []
    for c in cluster_dict:
        cluster_metrics = cluster_dict[c]
        if len(cluster_metrics) == 1:
            continue
        if len(cluster_metrics) == 2:
            # Select the representative metric at random
            shuffle_list = random.sample(cluster_metrics, len(cluster_metrics))
            clustering_info[target_df.columns[shuffle_list[0]]] = [target_df.columns[shuffle_list[1]]]
            remove_list.append(target_df.columns[shuffle_list[1]])
        elif len(cluster_metrics) > 2:
            # Select medoid as the representative metric
            distances = []
            for met1 in cluster_metrics:
                dist_sum = 0
                for met2 in cluster_metrics:
                    if met1 != met2:
                        dist_sum += dist_matrix[met1][met2]
                distances.append(dist_sum)
            medoid = cluster_metrics[np.argmin(distances)]
            clustering_info[target_df.columns[medoid]] = []
            for r in cluster_metrics:
                if r != medoid:
                    remove_list.append(target_df.columns[r])
                    clustering_info[target_df.columns[medoid]].append(target_df.columns[r])
    return clustering_info, remove_list


def create_clusters(data, columns, service_name, n):
    words_list = [col[2:] for col in columns]
    init_labels = cluster_words(words_list, service_name, n)
    results = kshape(data, n, initial_clustering=init_labels)
    label = [0] * data.shape[0]
    cluster_center = []
    cluster_num = 0
    for res in results:
        if not res[1]:
            continue
        for i in res[1]:
            label[i] = cluster_num
        cluster_center.append(res[0])
        cluster_num += 1
    if len(set(label)) == 1:
        return None
    return (label, silhouette_score(data, label), cluster_center)


def select_representative_metric(data, cluster_metrics, columns, centroid):
    clustering_info = {}
    remove_list = []
    if len(cluster_metrics) == 1:
        return None, None
    if len(cluster_metrics) == 2:
        # Select the representative metric at random
        shuffle_list = random.sample(cluster_metrics, len(cluster_metrics))
        clustering_info[columns[shuffle_list[0]]] = [columns[shuffle_list[1]]]
        remove_list.append(columns[shuffle_list[1]])
    elif len(cluster_metrics) > 2:
        # Select the representative metric based on the distance from the centroid
        distances = []
        for met in cluster_metrics:
            distances.append(sbd(centroid, data[met]))
        representative_metric = cluster_metrics[np.argmin(distances)]
        clustering_info[columns[representative_metric]] = []
        for r in cluster_metrics:
            if r != representative_metric:
                remove_list.append(columns[r])
                clustering_info[columns[representative_metric]].append(
                    columns[r])
    return (clustering_info, remove_list)


def kshape_clustering(target_df, service_name, executor):
    future_list = []

    data = util.z_normalization(target_df.values.T)
    for n in np.arange(2, data.shape[0]):
        future_list.append(
            executor.submit(create_clusters, data,
                            target_df.columns, service_name, n)
        )
    labels, scores, centroids = [], [], []
    for future in futures.as_completed(future_list):
        cluster = future.result()
        if cluster is None:
            continue
        labels.append(cluster[0])
        scores.append(cluster[1])
        centroids.append(cluster[2])

    idx = np.argmax(scores)
    label = labels[idx]
    centroid = centroids[idx]
    cluster_dict = {}
    for i, v in enumerate(label):
        if v not in cluster_dict:
            cluster_dict[v] = [i]
        else:
            cluster_dict[v].append(i)

    future_list = []
    for c, cluster_metrics in cluster_dict.items():
        future_list.append(
            executor.submit(select_representative_metric, data,
                            cluster_metrics, target_df.columns, centroid[c])
        )
    clustering_info = {}
    remove_list = []
    for future in futures.as_completed(future_list):
        c_info, r_list = future.result()
        if c_info is None:
            continue
        clustering_info.update(c_info)
        remove_list.extend(r_list)

    return clustering_info, remove_list


def tsifter_reduce_series(data_df, max_workers):
    reduced_by_st_df = pd.DataFrame()
    with futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_col = {}
        for col in data_df.columns:
            data = data_df[col].values
            if data.sum() == 0. or len(np.unique(data)) == 1 or np.isnan(data.sum()):
                continue
            future_to_col[executor.submit(adfuller, data)] = col
        for future in futures.as_completed(future_to_col):
            col = future_to_col[future]
            p_val = future.result()[1]
            if not np.isnan(p_val):
                if p_val >= SIGNIFICANCE_LEVEL:
                    reduced_by_st_df[col] = data_df[col]
    return reduced_by_st_df


def sieve_reduce_series(data_df):
    return reduce_series_with_cv(data_df)


def tsifter_clustering(reduced_by_st_df, services_list, max_workers):
    clustering_info = {}
    reduced_df = reduced_by_st_df

    with futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Clustering metrics by service including services, containers and middlewares metrics
        future_list = []
        for ser in services_list:
            target_df = reduced_by_st_df.loc[:, reduced_by_st_df.columns.str.startswith(
                ("s-{}_".format(ser), "c-{}_".format(ser), "c-{}-".format(ser), "m-{}_".format(ser), "m-{}-".format(ser)))]
            if len(target_df.columns) in [0, 1]:
                continue
            future_list.append(executor.submit(hierarchical_clustering, target_df, sbd))
        for future in futures.as_completed(future_list):
            c_info, remove_list = future.result()
            clustering_info.update(c_info)
            reduced_df = reduced_df.drop(remove_list, axis=1)

    return reduced_df, clustering_info


def sieve_clustering(reduced_by_cv_df, services_list, max_workers):
    clustering_info = {}
    reduced_df = reduced_by_cv_df

    with futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Clustering metrics by services including services, containers and middlewares
        for ser in services_list:
            target_df = reduced_by_cv_df.loc[:, reduced_by_cv_df.columns.str.startswith(
                ("s-{}_".format(ser), "c-{}_".format(ser), "c-{}-".format(ser), "m-{}_".format(ser), "m-{}-".format(ser)))]
            if len(target_df.columns) in [0, 1]:
                continue
            c_info, remove_list = kshape_clustering(target_df, ser, executor)
            clustering_info.update(c_info)
            reduced_df = reduced_df.drop(remove_list, axis=1)
    
    return reduced_df, clustering_info


def run_tsifter(data_df, metrics_dimension, services_list, max_workers):
    # step1
    start = time.time()

    reduced_by_st_df = tsifter_reduce_series(data_df, max_workers)

    time_adf = round(time.time() - start, 2)
    metrics_dimension = util.count_metrics(metrics_dimension, reduced_by_st_df, 1)
    metrics_dimension["total"].append(len(reduced_by_st_df.columns))

    # step2
    start = time.time()

    reduced_df, clustering_info = tsifter_clustering(
        reduced_by_st_df, services_list, max_workers)

    time_clustering = round(time.time() - start, 2)
    metrics_dimension = util.count_metrics(metrics_dimension, reduced_df, 2)
    metrics_dimension["total"].append(len(reduced_df.columns))

    return {'step1': time_adf, 'step2': time_clustering}, \
        reduced_df, metrics_dimension, clustering_info


def run_sieve(data_df, metrics_dimension, services_list, max_workers):
    # step1
    start = time.time()

    reduced_by_st_df = sieve_reduce_series(data_df)

    time_cv = round(time.time() - start, 2)
    metrics_dimension = util.count_metrics(metrics_dimension, reduced_by_st_df, 1)
    metrics_dimension["total"].append(len(reduced_by_st_df.columns))

    # step2
    start = time.time()

    reduced_df, clustering_info = sieve_clustering(
        reduced_by_st_df, services_list, max_workers)

    time_clustering = round(time.time() - start, 2)
    metrics_dimension = util.count_metrics(metrics_dimension, reduced_df, 2)
    metrics_dimension["total"].append(len(reduced_df.columns))

    return {'step1': time_cv, 'step2': time_clustering}, \
        reduced_df, metrics_dimension, clustering_info


def read_metrics_json(data_file):
    raw_data = pd.read_json(data_file)
    data_df = pd.DataFrame()
    for target in TARGET_DATA:
        for t in raw_data[target].dropna():
            for metric in t:
                if metric["metric_name"] in TARGET_DATA[target] or TARGET_DATA[target] == "all":
                    metric_name = metric["metric_name"].replace("container_", "").replace("node_", "")
                    target_name = metric[
                        "{}_name".format(target[:-1]) if target != "middlewares" else "container_name"].replace(
                        "gke-sock-shop-01-default-pool-", "")
                    if re.match("^gke-sock-shop-01", target_name):
                        continue
                    if target_name in ["queue-master", "rabbitmq", "session-db"]:
                        continue
                    column_name = "{}-{}_{}".format(target[0], target_name, metric_name)
                    data_df[column_name] = np.array(metric["values"], dtype=np.float64)[:, 1][-PLOTS_NUM:]
    data_df = data_df.round(4)
    data_df = data_df.interpolate(method="spline", order=3, limit_direction="both")
    return data_df, raw_data['mappings'].to_dict()


def prepare_services_list(data_df):
    # Prepare list of services
    services_list = []
    for col in data_df.columns:
        if re.match("^s-", col):
            service_name = col.split("_")[0].replace("s-", "")
            if service_name not in services_list:
                services_list.append(service_name)
    return services_list


def aggregate_dimension(data_df):
    metrics_dimension = {}
    for target in TARGET_DATA:
        metrics_dimension[target] = {}
    metrics_dimension = util.count_metrics(metrics_dimension, data_df, 0)
    metrics_dimension["total"] = [len(data_df.columns)]
    return metrics_dimension


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("datafile", help="metrics JSON data file")
    parser.add_argument("--method",
                        help="specify one of tsdr methods",
                        type=str, default=TSIFTER_METHOD)
    parser.add_argument("--max-workers",
                        help="number of processes",
                        type=int, default=1)
    parser.add_argument("--plot-num",
                        help="number of plots",
                        type=int, default=PLOTS_NUM)
    parser.add_argument("--metric-num",
                        help="number of metrics (for experiment)",
                        type=int, default=None)
    parser.add_argument("--out", help="output path", type=str)
    parser.add_argument("--results-dir",
                        help="output directory",
                        action='store_true')
    parser.add_argument("--include-raw-data",
                        help="include time series to results",
                        action='store_true')
    args = parser.parse_args()

    data_df, mappings = read_metrics_json(args.datafile)
    services = prepare_services_list(data_df)

    metrics_dimension = aggregate_dimension(data_df)

    if args.method == TSIFTER_METHOD:
        elapsedTime, reduced_df, metrics_dimension, clustering_info = run_tsifter(
            data_df, metrics_dimension, services, args.max_workers)
    elif args.method == SIEVE_METHOD:
        elapsedTime, reduced_df, metrics_dimension, clustering_info = run_sieve(
            data_df, metrics_dimension, services, args.max_workers)
    else:
        print("--method must be {} or {}",
              TSIFTER_METHOD, SIEVE_METHOD, file=sys.stderr)
        exit(-1)

    summary = {}
    summary["data_file"] = args.datafile.split("/")[-1]
    summary["number_of_plots"] = PLOTS_NUM
    summary["execution_time"] = {
        "reduce_series": elapsedTime['step1'],
        "clustering": elapsedTime['step2'],
        "total": round(elapsedTime['step1']+elapsedTime['step2'], 2)
    }
    summary["metrics_dimension"] = metrics_dimension
    summary["reduced_metrics"] = list(reduced_df.columns)
    summary["clustering_info"] = clustering_info
    summary["components_mappings"] = mappings
    if args.include_raw_data:
        summary["reduced_metrics_raw_data"] = reduced_df.to_dict()

    if args.results_dir:
        file_name = "{}_{}.json".format(
                TSIFTER_METHOD, datetime.now().strftime("%Y%m%d%H%M%S"))
        result_dir = "./results/{}".format(args.datafile.split("/")[-1])
        if not os.path.isdir(result_dir):
            os.makedirs(result_dir)
        with open(os.path.join(result_dir, file_name), "w") as f:
            json.dump(summary, f, indent=4)

    # print out, too.
    if args.out is None:
        json.dump(summary, sys.stdout)
    else:
        with open(args.out, mode='w') as f:
            json.dump(summary, f)


if __name__ == '__main__':
    # Disable multithreading in numpy.
    # see https://stackoverflow.com/questions/30791550/limit-number-of-threads-in-numpy
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
    os.environ["NUMEXPR_NUM_THREADS"] = "1"
    main()
