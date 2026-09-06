------------------------- MODULE RehomeTransaction -------------------------
EXTENDS Naturals, TLC

CONSTANT Fault

VARIABLES phase,
          sourceRevision,
          snapshotRevision,
          destinationRevision,
          destinationReady,
          destinationObserved,
          sourceArchived,
          establishAttempts,
          archiveAttempts

vars == << phase, sourceRevision, snapshotRevision, destinationRevision,
           destinationReady, destinationObserved, sourceArchived,
           establishAttempts, archiveAttempts >>

Init ==
  /\ phase = "preflight"
  /\ sourceRevision = 0
  /\ snapshotRevision = 2
  /\ destinationRevision = 2
  /\ destinationReady = FALSE
  /\ destinationObserved = FALSE
  /\ sourceArchived = FALSE
  /\ establishAttempts = 0
  /\ archiveAttempts = 0

BeginEstablish ==
  /\ phase = "preflight"
  /\ phase' = "establishing"
  /\ snapshotRevision' = sourceRevision
  /\ establishAttempts' = establishAttempts + 1
  /\ UNCHANGED << sourceRevision, destinationRevision, destinationReady,
                  destinationObserved, sourceArchived, archiveAttempts >>

SourceAdvances ==
  /\ ~sourceArchived
  /\ sourceRevision = 0
  /\ phase \in {"establishing", "ready"}
  /\ sourceRevision' = 1
  /\ UNCHANGED << phase, snapshotRevision, destinationRevision,
                  destinationReady, destinationObserved, sourceArchived,
                  establishAttempts, archiveAttempts >>

DestinationReady ==
  /\ phase = "establishing"
  /\ phase' = "readback"
  /\ destinationRevision' = snapshotRevision
  /\ destinationReady' = TRUE
  /\ UNCHANGED << sourceRevision, snapshotRevision, destinationObserved,
                  sourceArchived, establishAttempts, archiveAttempts >>

ObserveDestination ==
  /\ phase = "readback"
  /\ phase' = "ready"
  /\ destinationObserved' = TRUE
  /\ UNCHANGED << sourceRevision, snapshotRevision, destinationRevision,
                  destinationReady, sourceArchived, establishAttempts,
                  archiveAttempts >>

InstallResidual ==
  /\ phase = "establishing"
  /\ phase' = "retained"
  /\ UNCHANGED << sourceRevision, snapshotRevision, destinationRevision,
                  destinationReady, destinationObserved, sourceArchived,
                  establishAttempts, archiveAttempts >>

Archive ==
  \* This is the one source Codex App archive call, not an executable-owned RPC.
  /\ phase = "ready"
  /\ destinationObserved
  /\ (Fault = "ignoreSourceChange" \/ sourceRevision = destinationRevision)
  /\ phase' = "archiving"
  /\ archiveAttempts' = archiveAttempts + 1
  /\ UNCHANGED << sourceRevision, snapshotRevision, destinationRevision,
                  destinationReady, destinationObserved, sourceArchived,
                  establishAttempts >>

RejectChangedSource ==
  /\ phase = "ready"
  /\ sourceRevision # destinationRevision
  /\ Fault # "ignoreSourceChange"
  /\ phase' = "retained"
  /\ UNCHANGED << sourceRevision, snapshotRevision, destinationRevision,
                  destinationReady, destinationObserved, sourceArchived,
                  establishAttempts, archiveAttempts >>

ArchiveEarlyFault ==
  /\ Fault = "archiveEarly"
  /\ phase = "establishing"
  /\ phase' = "archiving"
  /\ archiveAttempts' = archiveAttempts + 1
  /\ UNCHANGED << sourceRevision, snapshotRevision, destinationRevision,
                  destinationReady, destinationObserved, sourceArchived,
                  establishAttempts >>

ArchiveDone ==
  /\ phase = "archiving"
  /\ phase' = "done"
  /\ sourceArchived' = TRUE
  /\ UNCHANGED << sourceRevision, snapshotRevision, destinationRevision,
                  destinationReady, destinationObserved, establishAttempts,
                  archiveAttempts >>

RetryEstablishFault ==
  /\ Fault = "retryEstablish"
  /\ phase = "retained"
  /\ phase' = "establishing"
  /\ establishAttempts' = establishAttempts + 1
  /\ UNCHANGED << sourceRevision, snapshotRevision, destinationRevision,
                  destinationReady, destinationObserved, sourceArchived,
                  archiveAttempts >>

Terminal == phase \in {"done", "retained"}

TerminalStutter ==
  /\ Terminal
  /\ UNCHANGED vars

Next ==
  \/ BeginEstablish
  \/ SourceAdvances
  \/ DestinationReady
  \/ ObserveDestination
  \/ InstallResidual
  \/ Archive
  \/ RejectChangedSource
  \/ ArchiveEarlyFault
  \/ ArchiveDone
  \/ RetryEstablishFault
  \/ TerminalStutter

TypeOK ==
  /\ phase \in {"preflight", "establishing", "readback", "ready",
                  "archiving", "done", "retained"}
  /\ sourceRevision \in 0..1
  /\ snapshotRevision \in 0..2
  /\ destinationRevision \in 0..2
  /\ destinationReady \in BOOLEAN
  /\ destinationObserved \in BOOLEAN
  /\ sourceArchived \in BOOLEAN
  /\ establishAttempts \in 0..2
  /\ archiveAttempts \in 0..1

ArchiveAfterDestinationReady ==
  sourceArchived => destinationReady /\ destinationObserved

DoneContainsLatestSource ==
  phase = "done" =>
    /\ sourceArchived
    /\ destinationRevision = sourceRevision

MutationExactlyOnce ==
  /\ establishAttempts <= 1
  /\ archiveAttempts <= 1

EventuallyReported == <>Terminal

\* Liveness is conditional on the modeled completion actions remaining enabled.
\* External process or network response is not proved by this model.
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

=============================================================================
