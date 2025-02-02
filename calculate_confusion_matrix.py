#!/usr/bin/env python

import argparse, pickle, torch, videotransforms
import numpy as np
from torchvision import transforms
from torch.utils.data import DataLoader, SequentialSampler
from dataset import IVBSSDataset, collate_fn
from model import TemporalActionLocalization


def get_parse():
    parser = argparse.ArgumentParser()
    parser.add_argument('--face_video_dir', type=str, help='face video directory')
    parser.add_argument('--cabin_video_dir', type=str, help='cabin video directory')
    parser.add_argument('--test_data_path', type=str, help='path to the test data')
    parser.add_argument('--batch_size', default=4, type=int)
    parser.add_argument('--ckp_path', type=str, help='path to the loaded checkpoint')
    parser.add_argument('--pretrained_I3D_model', type=str, help='path to the pretrained I3D model')
    parser.add_argument('--num_classes', type=int, help='number of classes')
    args = parser.parse_args()
    return args


def load_ckp(ckp_path, model):
    checkpoint = torch.load(ckp_path)
    model.load_state_dict(checkpoint['model'])
    return model


def calculate_confusion_matrix():
    args = get_parse()
    face_video_dir = args.face_video_dir
    cabin_video_dir = args.cabin_video_dir
    test_data_path = args.test_data_path
    batch_size = args.batch_size
    pretrained_I3D_model = args.pretrained_I3D_model
    num_classes = args.num_classes

    print('Start to load data')
    test_transforms = transforms.Compose([videotransforms.CenterCrop(224),
                                          videotransforms.ToTensor()
                                          ])
    test_dataset = IVBSSDataset(face_video_dir,
                                cabin_video_dir,
                                test_data_path,
                                test_transforms
                                )
    print('Total number of test samples is {0}'.format(len(test_dataset)))
    test_dataloader = DataLoader(test_dataset,
                                 batch_size=batch_size,
                                 sampler=SequentialSampler(test_dataset),
                                 collate_fn=collate_fn
                                 )
    model = TemporalActionLocalization(num_classes, pretrained_I3D_model)
    print('Load checkpoint')
    model = load_ckp(args.ckp_path, model)
    model.cuda()
    model.eval()

    print('Start to calculate confusion matrix')
    confusion_matrix = np.zeros([num_classes, num_classes])
    for i, (face_imgs, cabin_imgs, labels) in enumerate(test_dataloader):
        face_imgs = face_imgs.cuda()
        cabin_imgs = cabin_imgs.cuda()
        for k, v in labels.items():
            labels[k] = v.cuda()
        class_labels = labels['event_id']
        # start_labels = labels['start']
        # end_labels = labels['end']
        # rst_labels = labels['rst']
        # rend_labels = labels['rend']
        with torch.no_grad():
            class_scores = model(face_imgs, cabin_imgs, labels)[2]
        class_preds = torch.argmax(class_scores, dim=1)
        num = class_preds.shape[0]
        for j in range(num):
            class_label = class_labels[j]
            class_pred = class_preds[j]
            confusion_matrix[(class_label, class_pred)] += 1
    return confusion_matrix


if __name__ == '__main__':
    confusion_matrix = calculate_confusion_matrix()
    with open('train_confusion_matrix.pickle', 'wb') as f:
        pickle.dump(confusion_matrix, f)