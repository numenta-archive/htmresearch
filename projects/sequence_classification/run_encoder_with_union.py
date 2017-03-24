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

"""
Run sequence classification experiment with
Input -> RDSE encoder -> Union model
Search for the optimal union window

One needs to run the script "run_encoder_only.py" first to get the
optimal encoder resolution

"""

import pickle
import time
import matplotlib.pyplot as plt
import multiprocessing
from util_functions import *
from nupic.encoders.random_distributed_scalar import RandomDistributedScalarEncoder

plt.ion()

import matplotlib as mpl
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams.update({'figure.autolayout': True})



def unionForOneSequence(activeColumns, unionLength=1):
  activeColumnTrace = []

  unionStepInBatch = 0
  unionBatchIdx = 0
  unionCols = set()
  for t in range(len(activeColumns)):
    unionCols = unionCols.union(activeColumns[t])

    unionStepInBatch += 1
    if unionStepInBatch == unionLength:
      activeColumnTrace.append(unionCols)
      unionStepInBatch = 0
      unionBatchIdx += 1
      unionCols = set()

  if unionStepInBatch > 0:
    activeColumnTrace.append(unionCols)

  return activeColumnTrace



def runUnionStep(activeColumns, unionLength=1):
  """
  Run encoder -> tm network over dataset, save activeColumn and activeCells
  traces
  :param tm:
  :param encoder:
  :param dataset:
  :return:
  """
  numSequence = len(activeColumns)
  activeColumnUnionTrace = []

  for i in range(numSequence):
    activeColumnTrace = unionForOneSequence(activeColumns[i], unionLength)
    activeColumnUnionTrace.append(activeColumnTrace)
    # print "{} out of {} done ".format(i, numSequence)
  return activeColumnUnionTrace



def runEncoderOverDataset(encoder, dataset):
  activeColumnsData = []

  for i in range(dataset.shape[0]):
    activeColumnsTrace = []

    for element in dataset[i, :]:
      encoderOutput = encoder.encode(element)
      activeColumns = set(np.where(encoderOutput > 0)[0])
      activeColumnsTrace.append(activeColumns)

    activeColumnsData.append(activeColumnsTrace)
  return activeColumnsData



def calcualteEncoderModelWorker(taskQueue, resultQueue, *args):
  while True:
    nextTask = taskQueue.get()
    print "Next task is : ", nextTask
    if nextTask is None:
      break
    nBuckets = nextTask["nBuckets"]
    accuracyColumnOnly = calculateEncoderModelAccuracy(nBuckets, *args)
    resultQueue.put({nBuckets: accuracyColumnOnly})
    print "Column Only model, Resolution: {} Accuracy: {}".format(
      nBuckets, accuracyColumnOnly)
  return



def calculateEncoderModelAccuracy(nBuckets, numCols, w, trainData, trainLabel):
  maxValue = np.max(trainData)
  minValue = np.min(trainData)

  resolution = (maxValue - minValue) / nBuckets
  encoder = RandomDistributedScalarEncoder(resolution, w=w, n=numCols)

  activeColumnsTrain = runEncoderOverDataset(encoder, trainData)
  distMatColumnTrain = calculateDistanceMatTrain(activeColumnsTrain)
  meanAccuracy, outcomeColumn = calculateAccuracy(distMatColumnTrain,
                                                  trainLabel, trainLabel)
  accuracyColumnOnly = np.mean(outcomeColumn)
  return accuracyColumnOnly



def runDataSet(dataName, datasetName):
  if not os.path.exists('results'):
    os.makedirs('results')
  trainData, trainLabel, testData, testLabel = loadDataset(dataName,
                                                           datasetName)
  numTest = len(testLabel)
  numTrain = len(trainLabel)
  sequenceLength = len(trainData[0])
  classList = np.unique(trainLabel).tolist()
  numClass = len(classList)

  print "Processing {}".format(dataName)
  print "Train Sample # {}, Test Sample # {}".format(numTrain, numTest)
  print "Sequence Length {} Class # {}".format(sequenceLength, len(classList))

  if (max(numTrain, numTest) * sequenceLength < 600 * 600):
    print "skip this small dataset for now"
    return

  try:
    unionLengthList = [1, 5, 10, 15, 20]
    for unionLength in unionLengthList:
      expResultTM = pickle.load(
        open('results/modelPerformance/{}_columnOnly_union_{}'.format(
        dataName, unionLength), 'r'))
    return
  except:
    print "run data set: ", dataName

  EuclideanDistanceMat = calculateEuclideanDistanceMat(testData, trainData)
  outcomeEuclidean = calculateEuclideanModelAccuracy(trainData, trainLabel,
                                                     testData, testLabel)
  accuracyEuclideanDist = np.mean(outcomeEuclidean)
  print
  print "Euclidean model accuracy: {}".format(accuracyEuclideanDist)
  print

  # # Use SDR overlap instead of Euclidean distance
  print "Running Encoder model"
  maxValue = np.max(trainData)
  minValue = np.min(trainData)
  numCols = 2048
  w = 41

  try:
    searchResolution = pickle.load(
      open('results/optimalEncoderResolution/{}'.format(dataName), 'r'))
    nBucketList = searchResolution['nBucketList']
    accuracyVsResolution = searchResolution['accuracyVsResolution']
    optNumBucket = nBucketList[smoothArgMax(np.array(accuracyVsResolution))]
    optimalResolution = (maxValue - minValue) / optNumBucket
  except:
    return

  print "optimal bucket # {}".format((maxValue - minValue) / optimalResolution)

  encoder = RandomDistributedScalarEncoder(optimalResolution, w=w, n=numCols)
  print "encoding train data ..."
  activeColumnsTrain = runEncoderOverDataset(encoder, trainData)
  print "encoding test data ..."
  activeColumnsTest = runEncoderOverDataset(encoder, testData)
  print "calculate column distance matrix ..."

  # run encoder -> union model, search for the optimal union window
  unionLengthList = [1, 5, 10, 15, 20]
  for unionLength in unionLengthList:
    activeColumnUnionTrain = runUnionStep(activeColumnsTrain, unionLength)
    activeColumnUnionTest = runUnionStep(activeColumnsTest, unionLength)

    distMatColumnTrain = calculateDistanceMatTrain(activeColumnUnionTrain)
    distMatColumnTest = calculateDistanceMat(activeColumnUnionTest,
                                             activeColumnUnionTrain)

    trainAccuracyColumnOnly, outcomeColumn = calculateAccuracy(distMatColumnTest,
                                                              trainLabel,
                                                              testLabel)

    testAccuracyColumnOnly, outcomeColumn = calculateAccuracy(distMatColumnTest,
                                                              trainLabel,
                                                              testLabel)

    expResults = {'distMatColumnTrain': distMatColumnTrain,
                  'distMatColumnTest': distMatColumnTest,
                  'trainAccuracyColumnOnly': trainAccuracyColumnOnly,
                  'testAccuracyColumnOnly': testAccuracyColumnOnly}
    if not os.path.exists('results/distanceMat'):
      os.makedirs('results/distanceMat')
    outputFile = open('results/distanceMat/{}_columnOnly_union_{}'.format(
      dataName, unionLength), 'w')
    pickle.dump(expResults, outputFile)
    outputFile.close()
    print '--> wrote results to "results/distanceMat"'



def runDataSetWorker(taskQueue, datasetName):
  while True:
    nextTask = taskQueue.get()
    print "Next task is : ", nextTask
    if nextTask is None:
      break
    dataName = nextTask["dataName"]
    runDataSet(dataName, datasetName)
  return



if __name__ == "__main__":
  datasetName = "SyntheticData"
  dataSetList = listDataSets(datasetName)

  datasetName = 'UCR_TS_Archive_2015'
  dataSetList = listDataSets(datasetName)
  # dataSetList = ["synthetic_control"]

  numCPU = multiprocessing.cpu_count()
  numWorker = 2
  # Establish communication queues
  taskQueue = multiprocessing.JoinableQueue()

  for dataName in dataSetList:
    taskQueue.put({"dataName": dataName,
                   "datasetName": datasetName})
  for _ in range(numWorker):
    taskQueue.put(None)
  jobs = []
  for i in range(numWorker):
    print "Start process ", i
    p = multiprocessing.Process(target=runDataSetWorker,
                                args=(taskQueue, datasetName))
    jobs.append(p)
    p.daemon = True
    p.start()

  while not taskQueue.empty():
    time.sleep(5)
