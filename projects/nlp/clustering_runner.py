#!/usr/bin/env python
# ----------------------------------------------------------------------
# Numenta Platform for Intelligent Computing (NuPIC)
# Copyright (C) 2016, Numenta, Inc.  Unless you have purchased from
# Numenta, Inc. a separate commercial license for this software code, the
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

import argparse
import numpy
import os
import simplejson
from textwrap import TextWrapper
import matplotlib.pyplot as plt

from htmresearch.support.csv_helper import (
  readCSV, mapLabelRefs, readDataAndReshuffle)
from htmresearch.algorithms.hierarchical_clustering import (
  HierarchicalClustering
)
from htmresearch.frameworks.nlp.model_factory import (
  getNetworkConfig, createModel
)

SAVE_PATH = os.path.join(os.path.dirname(__file__),
                         "results/HierarchicalClustering/")


def runExperiment(args):
  if not os.path.exists(SAVE_PATH):
    os.makedirs(SAVE_PATH)
  
  (trainingDataDup, labelRefs, documentCategoryMap,
   documentTextMap) = readDataAndReshuffle(args)
  
  # remove duplicates from training data
  includedDocIds = set()
  trainingData = []
  for record in trainingDataDup:
    if record[2] not in includedDocIds:
      includedDocIds.add(record[2])
      trainingData.append(record)
  
  args.networkConfig = getNetworkConfig(args.networkConfigPath)
  model = createModel(numLabels=1, **vars(args))
  model = trainModel(args, model, trainingData, labelRefs)
  
  numDocs = model.getClassifier()._numPatterns
  
  print "Model trained with %d documents" % (numDocs,)
  
  knn = model.getClassifier()
  hc = HierarchicalClustering(knn)
  
  hc.cluster("complete")
  protos, clusterSizes = hc.getClusterPrototypes(args.numClusters,
                                                 numDocs)

  # Run test to ensure consistency with KNN
  if args.knnTest:
    knnTest(protos, knn)
    return


  # Summary statistics
  # bucketCounts[i, j] is the number of occurrances of bucket j in cluster i
  bucketCounts = numpy.zeros((args.numClusters, len(labelRefs)))  

  for clusterId in xrange(len(clusterSizes)):
    print
    print "Cluster %d with %d documents" % (clusterId, clusterSizes[clusterId])
    print "==============="

    prototypeNum = 0
    for index in protos[clusterId]:
      if index != -1:
        docId = trainingData[index][2]
        prototypeNum += 1
        display = prototypeNum <= args.numPrototypes

        if display:
          print "(%d) %s" % (docId, trainingData[index][0])
          print "Buckets:"

        # The docId keys in documentCategoryMap are strings rather than ints
        if docId in documentCategoryMap:
          for bucketId in documentCategoryMap[docId]:
            bucketCounts[clusterId, bucketId] += 1
            if display:
              print "    ", labelRefs[bucketId]
        elif display:
          print "    <None>"
        if display:
          print "\n\n"

  createBucketClusterPlot(args, bucketCounts)
  create2DSVDProjection(args, protos, trainingData, documentCategoryMap, knn)


def create2DSVDProjection(args, protos, trainingData, documentCategoryMap, knn):
  sparseDataMatrix = HierarchicalClustering._extractVectorsFromKNN(knn)
  covarianceMatrix = numpy.cov(sparseDataMatrix.toarray(), rowvar=0)
  u, s, v = numpy.linalg.svd(covarianceMatrix)
  projectionMatrix = numpy.dot(u[:,:2], numpy.diag(s[:2]))
  projectedData = sparseDataMatrix.dot(projectionMatrix)

  categoryCounts = []
  for document in documentCategoryMap:
    for category in documentCategoryMap[document]:
      if category >= len(categoryCounts):
        categoryCounts.extend([0] * (category - len(categoryCounts) + 1))
      categoryCounts[category] += 1
  categoryCounts = numpy.array(categoryCounts)

  colorSequenceBucket = []
  for docId in documentCategoryMap:
    buckets = documentCategoryMap[docId]
    counts = categoryCounts[buckets]
    maxBucketIndex = numpy.argmax(counts)
    maxBucket = buckets[maxBucketIndex]
    colorSequenceBucket.append(maxBucket)

  plt.figure()
  plt.subplot(121, aspect="equal")
  plt.title("Bucket labels (%s)" % (args.modelName,))
  plt.xlabel("PC 2")
  plt.ylabel("PC 1")
  plt.scatter(projectedData[:,1], projectedData[:,0], c=colorSequenceBucket)
  
  colorSequenceClusters = numpy.zeros(len(colorSequenceBucket))
  clusterId = 0
  for dataIndices in protos:
    colorSequenceClusters[[d for d in dataIndices if d != -1]] = clusterId
    clusterId += 1
  
  plt.subplot(122, aspect="equal")
  plt.title("Clusters (%s)" % (args.modelName,))
  plt.xlabel("PC 2")
  plt.ylabel("PC 1")
  plt.scatter(projectedData[:,1], projectedData[:,0], c=colorSequenceClusters)
  plt.savefig(os.path.join(SAVE_PATH, "scatter.png"))

  plt.figure()
  plt.plot(s[:250])
  plt.xlabel("Singular value #")
  plt.ylabel("Singular value")
  plt.savefig(os.path.join(SAVE_PATH, "singular_values.png"))


def createBucketClusterPlot(args, bucketCounts):
  bucketCounts += 0
  bucketDist = bucketCounts / bucketCounts.sum(1, keepdims=True)
  
  plt.pcolor(bucketDist, cmap=plt.cm.Blues)
  # plt.bar(range(len(labelRefs)), bucketDist.T)
  plt.xlabel("Bucket")
  plt.ylabel("Cluster")
  plt.title("%d clusters using model %s" % (bucketCounts.shape[0], args.modelName))
    
  for rowIx in xrange(bucketCounts.shape[0]):
    for colIx in xrange(bucketCounts.shape[1]):
      if bucketCounts[rowIx, colIx] != 0:
        plt.annotate(str(int(bucketCounts[rowIx, colIx])), xy=(colIx+0.2, rowIx+0.4))

  plt.savefig(os.path.join(SAVE_PATH, "bucket_cluster_matrix.png"))
  


def knnTest(protos, knn):
  print "Running KNN Test"
  testPassed = True
  protoSets = [set(protoList)-set([-1]) for protoList in protos]

  for cluster in protoSets:
    if len(cluster) == 1:
      continue
      
    for index in cluster:
      if index != -1:
        # print index
        testPattern = knn.getPattern(index)
        allDistances = knn._getDistances(testPattern)
        closest = allDistances.argmin()
        # print closest
        if closest not in cluster:
          testPassed = False
  if testPassed:
    print "KNN test passed"
  else:
    print "KNN test failed"


def trainModel(args, model, trainingData, labelRefs):
  """
  Train the given model on trainingData. Return the trained model instance.
  """
  print
  print "=======================Training model on sample text================"
  for docId, doc in enumerate(trainingData):
    document = doc[0]
    labels = doc[1]
    print
    print "Document=", document, "label=",labelRefs[doc[1][0]], "id=",docId
    model.trainDocument(document, labels, docId)

  return model


if __name__ == "__main__":

  parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    # description=helpStr
  )

  parser.add_argument("-m", "--modelName",
                      default="cioword",
                      type=str,
                      help="Name of model class. Options: [docfp, cioword]")
  parser.add_argument("--retinaScaling",
                      default=1.0,
                      type=float,
                      help="Factor by which to scale the Cortical.io retina.")
  parser.add_argument("--numClusters",
                      default=8,
                      type=int,
                      help="Number of clusters to form.")
  parser.add_argument("--numPrototypes",
                      default=3,
                      type=int,
                      help="Maximum number of prototypes to return per cluster.")
  parser.add_argument("--retina",
                      default="en_associative_64_univ",
                      type=str,
                      help="Name of Cortical.io retina.")
  parser.add_argument("--apiKey",
                      default=None,
                      type=str,
                      help="Key for Cortical.io API. If not specified will "
                      "use the environment variable CORTICAL_API_KEY.")
  parser.add_argument("--modelDir",
                      default="MODELNAME.checkpoint",
                      help="Model will be saved in this directory.")
  parser.add_argument("--dataPath",
                      default=None,
                      help="CSV file containing labeled dataset")
  parser.add_argument("--knnTest",
                      default=False,
                      action='store_true',
                      help="Run test for consistency with KNN")
  parser.add_argument("-v", "--verbosity",
                      default=2,
                      type=int,
                      help="verbosity 0 will print out experiment steps, "
                           "verbosity 1 will include results, and verbosity > "
                           "1 will print out preprocessed tokens and kNN "
                           "inference metrics.")
  parser.add_argument("-c", "--networkConfigPath",
                      default="data/network_configs/sensor_knn.json",
                      help="Path to JSON specifying the network params.",
                      type=str)
  args = parser.parse_args()

  # By default set checkpoint directory name based on model name
  if args.modelDir == "MODELNAME.checkpoint":
    args.modelDir = args.modelName + ".checkpoint"

  model = runExperiment(args)
