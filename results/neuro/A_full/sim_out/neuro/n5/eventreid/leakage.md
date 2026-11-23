# N5 leakage

Chance level 0.030; 17 test clusters. Classifiers n/a: every test label is a group never seen in training (label = group, e.g. Event-ReId persons), so only MI is reported.

| view | MI bits (total count) | p (perm.) | bal. acc. nearest-centroid | bal. acc. 5-NN |
|---|---|---|---|---|
| V2 | 0.8058 | 0.9652 | n/a | n/a |
| V3 | 0.8058 | 0.9652 | n/a | n/a |
| V3 + pad floor 4 | 0.7852 | 0.9801 | n/a | n/a |
| V3 + pad floor 16 | 0.9616 | 0.4279 | n/a | n/a |
| V3 + pad ladder 2..64 | 0.8058 | 0.9502 | n/a | n/a |
| V4 | 0.7852 | 0.9801 | n/a | n/a |
| V4 + pad floor 4 | 0.7027 | 1 | n/a | n/a |
| V4 + pad ladder 2..64 | 0.8058 | 0.9353 | n/a | n/a |

Dummy distinguisher AUC (0.5 = indistinguishable):

| policy | multiplicity | position | both | CD words |
|---|---|---|---|---|
| floor 4 | 0.5004 | 0.9005 | 0.9006 | 4147661 |
| floor 16 | 0.5004 | 0.8174 | 0.8175 | 7908862 |
| ladder 2..64 | 0.5003 | 0.7681 | 0.7681 | 5146691 |

| policy | dummies per real CD word | buckets above PAD_MIN/PAD_CAP |
|---|---|---|
| floor 4 | 0.06775 | 0.6056 |
| floor 16 | 0.6763 | 0.2601 |
| ladder 2..64 | 0.3917 | 0.005248 |
