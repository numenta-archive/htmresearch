# ----------------------------------------------------------------------
# Numenta Platform for Intelligent Computing (NuPIC)
# Copyright (C) 2016, Numenta, Inc.  Unless you have an agreement
# with Numenta, Inc., for a separate license for this software code, the
# following terms and conditions apply:
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero Public License for more details.
#
# You should have received a copy of the GNU Affero Public License
# along with this program.  If not, see http://www.gnu.org/licenses.
#
# http://numenta.org/licenses/
# ----------------------------------------------------------------------
import csv
import os
import scipy
import numpy as np
from sklearn import manifold

from distances import cluster_distance_factory



def moving_average(last_ma, new_point_value, moving_average_window):
  """
  Online computation of moving average.
  From: http://www.daycounter.com/LabBook/Moving-Average.phtml
  """

  ma = last_ma + (new_point_value - last_ma) / float(moving_average_window)
  return ma



def clustering_stats(record_number,
                     clusters,
                     closest_cluster,
                     actual_category,
                     num_correct,
                     clustering_accuracy,
                     moving_average_window):
  if closest_cluster:
    # info about predicted cluster. The predicted cluster category is the 
    # most frequent category found in the points of the cluster.
    category_frequencies = closest_cluster.label_distribution()
    cluster_category = category_frequencies[0]['label']

    # compute accuracy      
    if cluster_category == actual_category:
      accuracy = 1.0
    else:
      accuracy = 0.0
    num_correct += accuracy

    cluster_id = closest_cluster.id
    cluster_size = closest_cluster.size

    print("Record: %s | Total clusters: %s | "
          "Closest: {id=%s, size=%s, category=%s} | Actual category: %s"
          % (record_number, len(clusters), cluster_id,
             cluster_size, cluster_category, actual_category))
  else:
    # If no cluster is predicted, consider this a wrong prediction.
    accuracy = 0.0

  clustering_accuracy = moving_average(clustering_accuracy, accuracy,
                                       moving_average_window)

  return clustering_accuracy



def get_file_name(exp_name, network_config):
  trace_csv = os.path.join('traces', '%s_%s.csv' % (exp_name, network_config))
  return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      os.pardir, 'classification', 'results',
                      trace_csv)



def convert_to_sdr(patternNZ, input_width):
  sdr = np.zeros(input_width)
  sdr[np.array(patternNZ, dtype='int')] = 1
  return sdr



def convert_to_sdrs(patterNZs, input_width):
  sdrs = []
  for i in range(len(patterNZs)):
    patternNZ = patterNZs[i]
    sdr = np.zeros(input_width, dtype='int32')
    sdr[patternNZ] = 1
    sdrs.append(sdr)
  return sdrs



def load_csv(input_file):
  with open(input_file, 'r') as f:
    reader = csv.reader(f)
    headers = reader.next()
    points = []
    labels = []
    for row in reader:
      dict_row = dict(zip(headers, row))
      points.append(scipy.array([float(dict_row['x']),
                                 float(dict_row['y'])]))
      labels.append(int(dict_row['label']))

    return points, labels



def get_num_clusters(cluster_ids):
  """
  Return the number of actual clusters.
  Note that noise is labelled as category 0, but that there might not be 
  noise in this dataset.

  :param cluster_ids: (list) cluster IDs
  :return num_clusters: (int) number of unique clusters 
  """
  unique_clusters = np.unique(cluster_ids)
  num_categories = len(unique_clusters)
  if 0 not in unique_clusters:
    num_categories += 1

  return num_categories



def find_cluster_repetitions(sdrs, cluster_ids):
  """
  Find how many times a cluster IDs is assigned to a consecutive sequence of 
  points.
  :param sdrs: (list of np.array)
  :param cluster_ids: (list) cluster IDs
  :return cluster_repetitions: (list) repetition count of consecutive sequence 
    of points with the same cluster ID.
  :return sdr_clusters: (dict of list) keys are the cluster IDs. Values are 
    the SDRs in the cluster.
  """
  unique_cluster_ids = list(set(cluster_ids))
  repetition_counter = {cluster_id: 0 for cluster_id in unique_cluster_ids}
  last_category = None
  cluster_repetitions = []
  sdr_clusters = {cluster_id: [] for cluster_id in unique_cluster_ids}
  for i in range(len(cluster_ids)):
    category = cluster_ids[i]
    sdr = sdrs[i]
    if category != last_category:
      repetition_counter[category] += 1
    last_category = category
    cluster_repetitions.append(repetition_counter[category] - 1)
    sdr_clusters[category].append(sdr)

  assert len(cluster_ids) == sum([len(sdr_clusters[cluster_id])
                                  for cluster_id in unique_cluster_ids])

  return cluster_repetitions, sdr_clusters



def find_cluster_assignments(sdrs, cluster_ids, ignore_noise):
  """
  Compare inter-cluster distance over time.
  :param sdrs: (list of np.array) list of sdr
  :param cluster_ids: (list) name of the cluster field in the traces dict
  :param ignore_noise: (bool) whether to take noise (label=0) into account
  :return: 
  """

  cluster_reps, sdr_clusters = find_cluster_repetitions(sdrs, cluster_ids)

  num_reps_per_category = {}
  categories = list(np.unique(cluster_ids))
  repetition = np.array(cluster_reps)
  for category in categories:
    num_reps_per_category[category] = np.max(
      repetition[np.array(cluster_ids) == category])

  sdr_slices = []
  cluster_assignments = []
  min_num_reps = np.min(num_reps_per_category.values()).astype('int32')
  for rpt in range(min_num_reps + 1):
    idx0 = np.logical_and(np.array(cluster_ids) == 0, repetition == rpt)
    idx1 = np.logical_and(np.array(cluster_ids) == 1, repetition == rpt)
    idx2 = np.logical_and(np.array(cluster_ids) == 2, repetition == rpt)

    c0slice = [sdrs[i] for i in range(len(idx0)) if idx0[i]]
    c1slice = [sdrs[i] for i in range(len(idx1)) if idx1[i]]
    c2slice = [sdrs[i] for i in range(len(idx2)) if idx2[i]]

    if not ignore_noise:
      sdr_slices.append(c0slice)
      cluster_assignments.append(0)
    sdr_slices.append(c1slice)
    cluster_assignments.append(1)
    sdr_slices.append(c2slice)
    cluster_assignments.append(2)

  return cluster_assignments, sdr_slices



def cluster_distance_matrix(sdr_clusters, distance_func):
  """
  Compute distance matrix between clusters of SDRs
  :param sdr_clusters: list of sdr clusters. Each cluster is a list of SDRs.
  :return: distance matrix
  """

  cluster_dist = cluster_distance_factory(distance_func)

  num_clusters = len(sdr_clusters)
  distance_mat = np.zeros((num_clusters, num_clusters), dtype=np.float64)

  for i in range(num_clusters):
    for j in range(i, num_clusters):
      distance_mat[i, j] = cluster_dist(sdr_clusters[i],
                                        sdr_clusters[j])
      distance_mat[j, i] = distance_mat[i, j]

  return distance_mat



def project_clusters_2D(distance_mat, method='mds'):
  """
  Project SDRs onto a 2D space using manifold learning algorithms
  :param distance_mat: A square matrix with pairwise distances
  :param method: Select method from 'mds' and 'tSNE'
  :return: an array with dimension (numSDRs, 2). It contains the 2D projections
     of each SDR
  """
  seed = np.random.RandomState(seed=3)

  if method == 'mds':
    mds = manifold.MDS(n_components=2, max_iter=3000, eps=1e-9,
                       random_state=seed,
                       dissimilarity="precomputed", n_jobs=1)

    pos = mds.fit(distance_mat).embedding_

    nmds = manifold.MDS(n_components=2, metric=False, max_iter=3000, eps=1e-12,
                        dissimilarity="precomputed", random_state=seed,
                        n_jobs=1, n_init=1)

    pos = nmds.fit_transform(distance_mat, init=pos)
  elif method == 'tSNE':
    tsne = manifold.TSNE(n_components=2, init='pca', random_state=0)
    pos = tsne.fit_transform(distance_mat)
  else:
    raise NotImplementedError

  return pos
