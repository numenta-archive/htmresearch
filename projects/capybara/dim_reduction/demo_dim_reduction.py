#!/usr/bin/env python
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

import os

from htmresearch.frameworks.capybara.sdr import generate_sdrs
from htmresearch.frameworks.capybara.unsupervised.util import (
  computeDistanceMat,
  assignClusters,
  viz2DProjection,
  plotDistanceMat)
from htmresearch.frameworks.dimensionality_reduction.proj import project_in_2D



def main():

  methods = ['mds', 'tSNE']
  numClasses = 7
  numSDRsPerClass = 20
  noiseLevel = 0.1
  # SDR parameters
  n = 1024
  w = 20

  for method in methods:

    outputDir = 'plots_%s' %method
    if not os.path.exists(outputDir): os.makedirs(outputDir)
    vizTitle = '2D projection (%s) noise level: %s' % (method.upper(),
                                                       noiseLevel)

    sdrs, _ = generate_sdrs(numClasses, numSDRsPerClass, n, w, noiseLevel)

    clusterAssignments = assignClusters(sdrs, numClasses, numSDRsPerClass)

    mat = computeDistanceMat(sdrs)
    npos = project_in_2D(mat, method=method)

    outputFile = os.path.join(outputDir, '2d_projections_%s.png' % method)
    viz2DProjection(vizTitle, outputFile, numClasses, clusterAssignments, npos)
    outputFile = os.path.join(outputDir, 'distance_matrix_%s.png' % method)
    plotDistanceMat(mat, 'Inter-cluster distances', outputFile,
                    showPlot=False)
    print 'plots saved in:', outputDir



if __name__ == '__main__':
  main()
