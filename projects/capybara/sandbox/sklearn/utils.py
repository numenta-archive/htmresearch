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
import sys
import copy
import os
import numpy as np



def load_traces(input_dir, file_name):
  """
  Load network traces from CSV
  :param input_dir: (str) path to input data dir
  :param file_name: (str) name of the file
  :return traces: (dict) network traces. E.g: activeCells, sensorValues, etc.
  """

  csv.field_size_limit(sys.maxsize)

  input_path = os.path.join(input_dir, file_name)
  with open(input_path, 'rb') as fr:
    reader = csv.reader(fr)
    headers = reader.next()

    traces = dict()
    for field in headers:
      traces[field] = []

    for row in reader:
      for i in range(len(row)):
        if len(row[i]) == 0:
          data = []
        else:
          if headers[i] in ['tmPredictedActiveCells',
                            'tpActiveCells',
                            'tmActiveCells']:
            if row[i] == '[]':
              data = []
            else:
              data = map(int, row[i][1:-1].split(','))
          else:
            data = float(row[i])
        traces[headers[i]].append(data)

  return traces



def get_file_name(exp_name, network_config):
  trace_csv = os.path.join('traces', '%s_%s.csv' % (exp_name, 
                                                      network_config))
  return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      os.pardir, os.pardir, 'classification', 'results',
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



def generate_sdr(n, w):
  """
  Generate a random n-dimensional SDR with w bits active
  """
  sdr = np.zeros((n,))
  random_order = np.random.permutation(np.arange(n))
  active_bits = random_order[:w]
  sdr[active_bits] = 1
  return sdr



def corrupt_sparse_vector(sdr, noise_level):
  """
  Add noise to sdr by turning off num_noise_bits active bits and turning on
  num_noise_bits in active bits
  :param sdr: (array) Numpy array of the  SDR
  :param noise_level: (float) amount of noise to be applied on the vector.
  """
  num_noise_bits = int(noise_level * np.sum(sdr))
  if num_noise_bits <= 0:
    return sdr
  active_bits = np.where(sdr > 0)[0]
  inactive_bits = np.where(sdr == 0)[0]

  turn_off_bits = np.random.permutation(active_bits)
  turn_on_bits = np.random.permutation(inactive_bits)
  turn_off_bits = turn_off_bits[:num_noise_bits]
  turn_on_bits = turn_on_bits[:num_noise_bits]

  sdr[turn_off_bits] = 0
  sdr[turn_on_bits] = 1



def generate_sdrs(num_sdr_classes, num_sdr_per_class, n, w, noise_level):
  sdrs = []
  class_ids = []
  for class_id in range(num_sdr_classes):
    class_ids.append(class_id)
    template_sdr = generate_sdr(n, w)
    sdr_cluster = []
    for _ in range(num_sdr_per_class):
      noisy_sdr = copy.copy(template_sdr)
      corrupt_sparse_vector(noisy_sdr, noise_level)
      sdrs.append(noisy_sdr)
      sdr_cluster.append(noisy_sdr)
  return sdrs, class_ids
