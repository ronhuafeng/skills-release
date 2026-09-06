--------------------------- MODULE PartitionScan ---------------------------
EXTENDS Naturals, FiniteSets, TLC

CONSTANT Fault

Windows == 1..3

VARIABLES phase,
          sourceRevision,
          boundRevision,
          nextWindow,
          windowsRead,
          receipt,
          plan,
          staged,
          published,
          publishAttempts

vars == << phase, sourceRevision, boundRevision, nextWindow, windowsRead,
           receipt, plan, staged, published, publishAttempts >>

Init ==
  /\ phase = "inspect"
  /\ sourceRevision = 0
  /\ boundRevision = 0
  /\ nextWindow = 1
  /\ windowsRead = {}
  /\ receipt = FALSE
  /\ plan = FALSE
  /\ staged = FALSE
  /\ published = FALSE
  /\ publishAttempts = 0

ReadWindow ==
  /\ phase = "inspect"
  /\ sourceRevision = boundRevision
  /\ nextWindow \in Windows
  /\ windowsRead' = windowsRead \union {nextWindow}
  /\ nextWindow' = nextWindow + 1
  /\ IF nextWindow = 3 THEN receipt' = TRUE ELSE receipt' = receipt
  /\ UNCHANGED << phase, sourceRevision, boundRevision, plan, staged,
                  published, publishAttempts >>

SourceAdvances ==
  /\ sourceRevision = 0
  /\ phase \in {"inspect", "plan", "staging"}
  /\ sourceRevision' = 1
  /\ UNCHANGED << phase, boundRevision, nextWindow, windowsRead, receipt,
                  plan, staged, published, publishAttempts >>

RejectStale ==
  /\ phase \in {"inspect", "plan", "staging"}
  /\ sourceRevision # boundRevision
  /\ phase' = "rejected"
  /\ UNCHANGED << sourceRevision, boundRevision, nextWindow, windowsRead,
                  receipt, plan, staged, published, publishAttempts >>

BuildPlan ==
  /\ phase = "inspect"
  /\ receipt
  /\ sourceRevision = boundRevision
  /\ phase' = "plan"
  /\ plan' = TRUE
  /\ UNCHANGED << sourceRevision, boundRevision, nextWindow, windowsRead,
                  receipt, staged, published, publishAttempts >>

Stage ==
  /\ phase = "plan"
  /\ plan
  /\ sourceRevision = boundRevision
  /\ phase' = "staging"
  /\ staged' = TRUE
  /\ UNCHANGED << sourceRevision, boundRevision, nextWindow, windowsRead,
                  receipt, plan, published, publishAttempts >>

Publish ==
  /\ phase = "staging"
  /\ staged
  /\ sourceRevision = boundRevision
  /\ phase' = "published"
  /\ published' = TRUE
  /\ publishAttempts' = publishAttempts + 1
  /\ UNCHANGED << sourceRevision, boundRevision, nextWindow, windowsRead,
                  receipt, plan, staged >>

EarlyReceiptFault ==
  /\ Fault = "earlyReceipt"
  /\ phase = "inspect"
  /\ nextWindow < 4
  /\ receipt' = TRUE
  /\ UNCHANGED << phase, sourceRevision, boundRevision, nextWindow,
                  windowsRead, plan, staged, published, publishAttempts >>

SkipWindowFault ==
  /\ Fault = "skipWindow"
  /\ phase = "inspect"
  /\ nextWindow \in 1..2
  /\ nextWindow' = nextWindow + 2
  /\ windowsRead' = windowsRead \union {nextWindow + 1}
  /\ UNCHANGED << phase, sourceRevision, boundRevision, receipt, plan,
                  staged, published, publishAttempts >>

StalePublishFault ==
  /\ Fault = "stalePublish"
  /\ phase = "staging"
  /\ sourceRevision # boundRevision
  /\ phase' = "published"
  /\ published' = TRUE
  /\ publishAttempts' = publishAttempts + 1
  /\ UNCHANGED << sourceRevision, boundRevision, nextWindow, windowsRead,
                  receipt, plan, staged >>

RetryPublishFault ==
  /\ Fault = "retryPublish"
  /\ phase = "published"
  /\ publishAttempts = 1
  /\ publishAttempts' = 2
  /\ UNCHANGED << phase, sourceRevision, boundRevision, nextWindow,
                  windowsRead, receipt, plan, staged, published >>

Terminal == phase \in {"published", "rejected"}

TerminalStutter ==
  /\ Terminal
  /\ UNCHANGED vars

Next ==
  \/ ReadWindow
  \/ SourceAdvances
  \/ RejectStale
  \/ BuildPlan
  \/ Stage
  \/ Publish
  \/ EarlyReceiptFault
  \/ SkipWindowFault
  \/ StalePublishFault
  \/ RetryPublishFault
  \/ TerminalStutter

TypeOK ==
  /\ phase \in {"inspect", "plan", "staging", "published", "rejected"}
  /\ sourceRevision \in 0..1
  /\ boundRevision \in 0..1
  /\ nextWindow \in 1..4
  /\ windowsRead \subseteq Windows
  /\ receipt \in BOOLEAN
  /\ plan \in BOOLEAN
  /\ staged \in BOOLEAN
  /\ published \in BOOLEAN
  /\ publishAttempts \in 0..2

ContinuationIsPrefix == windowsRead = (1..(nextWindow - 1))

ReceiptAfterComplete == receipt => windowsRead = Windows

PlanAfterReceipt == plan => receipt /\ windowsRead = Windows

PublishedFresh ==
  published => plan /\ staged /\ sourceRevision = boundRevision

PublishExactlyOnce == publishAttempts <= 1

EventuallyReported == <>Terminal

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

=============================================================================
