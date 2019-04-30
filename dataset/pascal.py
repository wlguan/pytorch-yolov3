import numpy as np
from utils.dataset_util import PascalVocXmlParser
import cv2
from dataset.augment import transform
import os
from config import VOC_LABEL, VOC_ANCHOR_512, VOC_ANCHOR_480, TRAIN_INPUT_SIZES_VOC
import random
import torch


class VOCdataset:
  def __init__(self, dataset_root, transform, subset, batchsize, netsize, istrain):
    self.dataset_root = dataset_root
    self.labels = VOC_LABEL
    self.anchors = np.array(eval("VOC_ANCHOR_{}".format(netsize)))
    self._transform = transform
    self._annopath = os.path.join('{}', 'Annotations', '{}.xml')
    self._imgpath = os.path.join('{}', 'JPEGImages', '{}.jpg')
    self._ids = []
    self.netsize = netsize
    self.batch_size = batchsize
    self.multisizes = TRAIN_INPUT_SIZES_VOC
    self.istrain = istrain
    for year, set in subset:
      rootpath = os.path.join(dataset_root, 'VOC' + year)
      for line in open(os.path.join(rootpath, 'ImageSets', 'Main', '{}.txt'.format(set))):
        self._ids.append((rootpath, line.strip()))

  def __len__(self):
    return len(self._ids) // self.batch_size

  def _load_batch(self, idx_batch, random_trainsize):
    img_batch = []
    imgpath_batch = []
    annpath_batch = []
    pad_scale_batch = []
    ori_shape_batch = []
    grid0_batch = []
    grid1_batch = []
    grid2_batch = []
    for idx in range(self.batch_size):
      rootpath, filename = self._ids[idx_batch * self.batch_size + idx]
      annpath = self._annopath.format(rootpath, filename)
      imgpath = self._imgpath.format(rootpath, filename)
      fname, bboxes, labels, _ = PascalVocXmlParser(annpath, self.labels).parse()
      img = cv2.imread(imgpath, cv2.IMREAD_COLOR)
      img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
      ori_shape = img.shape[:2][::-1]  # yx-->xy
      # Load the annotation.
      img, bboxes = self._transform(random_trainsize, random_trainsize, img, bboxes)
      list_grids = transform.preprocess(bboxes, labels, img.shape[:2], class_num=len(self.labels), anchors=self.anchors)
      pad_scale = (1, 1)
      img_batch.append(img)
      imgpath_batch.append(imgpath)
      annpath_batch.append(annpath)
      ori_shape_batch.append(ori_shape)
      pad_scale_batch.append(pad_scale)
      grid0_batch.append(list_grids[0])
      grid1_batch.append(list_grids[1])
      grid2_batch.append(list_grids[2])
    return torch.from_numpy(np.array(img_batch).transpose((0, 3, 1, 2)).astype(np.float32)), \
           imgpath_batch, \
           annpath_batch, \
           torch.from_numpy(np.array(pad_scale_batch).astype(np.float32)), \
           torch.from_numpy(np.array(ori_shape_batch).astype(np.float32)), \
           torch.from_numpy(np.array(grid0_batch).astype(np.float32)), \
           torch.from_numpy(np.array(grid1_batch).astype(np.float32)), \
           torch.from_numpy(np.array(grid2_batch).astype(np.float32))

  def __getitem__(self, item):
    if self.istrain:
      trainsize = random.choice(self.multisizes)
    else:
      trainsize = self.netsize

    return self._load_batch(item, trainsize)


def get_dataset(dataset_root, batch_size, net_size):
  subset = [('2007', 'test')]
  datatransform = transform.YOLO3DefaultValTransform(mean=(0, 0, 0), std=(1, 1, 1))
  valset = VOCdataset(dataset_root, datatransform, subset, batch_size, net_size, istrain=False)

  valset = torch.utils.data.DataLoader(dataset=valset, batch_size=1, shuffle=False, num_workers=1, pin_memory=True)

  subset = [('2007', 'trainval'), ('2012', 'trainval')]
  datatransform = transform.YOLO3DefaultTrainTransform(mean=(0, 0, 0), std=(1, 1, 1))
  trainset = VOCdataset(dataset_root, datatransform, subset, batch_size, net_size, istrain=True)
  trainset = torch.utils.data.DataLoader(dataset=trainset, batch_size=1, shuffle=True, num_workers=1, pin_memory=True)
  return trainset, valset


if __name__ == '__main__':
  train,val=get_dataset('/home/gwl/datasets/VOCdevkit',8,480)
  print(len(train))
  print(len(val))
  for idx_batch, inputs in enumerate(train):
    inputs = [input if isinstance(input, list) else input.squeeze(0) for input in inputs]
    (imgs, imgpath, annpath, padscale, ori_shapes, *_) = inputs
    print(imgpath)
    # assert 0