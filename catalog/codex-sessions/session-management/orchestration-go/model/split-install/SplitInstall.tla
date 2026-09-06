---------------------------- MODULE SplitInstall ----------------------------
EXTENDS Naturals, FiniteSets, TLC

CONSTANT Fault

\* Three parts distinguish a completed prefix, the current part, and later work.
\* Mutation outcomes are nondeterministic. Only the following readback action
\* authorizes progress to the next effect.
Parts == 1..3

VARIABLES phase,
          current,
          completed,
          stoppedAt,
          filePresent,
          appVisible,
          projectBound,
          everFilePresent,
          everAppVisible,
          everProjectBound,
          fileCalls,
          resumeCalls,
          bindCalls,
          pendingEffect,
          mutationWhilePending,
          staging

vars == << phase, current, completed, stoppedAt, filePresent, appVisible,
           projectBound, everFilePresent, everAppVisible, everProjectBound,
           fileCalls, resumeCalls, bindCalls, pendingEffect,
           mutationWhilePending, staging >>

Init ==
  /\ phase = "fileCall"
  /\ current = 1
  /\ completed = {}
  /\ stoppedAt = 0
  /\ filePresent = {}
  /\ appVisible = {}
  /\ projectBound = {}
  /\ everFilePresent = {}
  /\ everAppVisible = {}
  /\ everProjectBound = {}
  /\ fileCalls = [p \in Parts |-> 0]
  /\ resumeCalls = [p \in Parts |-> 0]
  /\ bindCalls = [p \in Parts |-> 0]
  /\ pendingEffect = "none"
  /\ mutationWhilePending = FALSE
  /\ staging = Parts

InstallFile(effect) ==
  /\ phase = "fileCall"
  /\ pendingEffect = "none"
  /\ fileCalls[current] = 0
  /\ phase' = "fileReadback"
  /\ fileCalls' = [fileCalls EXCEPT ![current] = @ + 1]
  /\ pendingEffect' = "file"
  /\ filePresent' = IF effect THEN filePresent \union {current}
                                  ELSE filePresent
  /\ everFilePresent' = IF effect THEN everFilePresent \union {current}
                                      ELSE everFilePresent
  /\ UNCHANGED << current, completed, stoppedAt, appVisible, projectBound,
                  everAppVisible, everProjectBound, resumeCalls, bindCalls,
                  mutationWhilePending, staging >>

ReadFile ==
  /\ phase = "fileReadback"
  /\ pendingEffect = "file"
  /\ phase' = IF current \in filePresent THEN "resumeCall" ELSE "stopped"
  /\ stoppedAt' = IF current \in filePresent THEN stoppedAt ELSE current
  /\ pendingEffect' = "none"
  /\ UNCHANGED << current, completed, filePresent, appVisible, projectBound,
                  everFilePresent, everAppVisible, everProjectBound, fileCalls,
                  resumeCalls, bindCalls, mutationWhilePending, staging >>

ResumeApp(effect) ==
  /\ phase = "resumeCall"
  /\ pendingEffect = "none"
  /\ current \in filePresent
  /\ resumeCalls[current] = 0
  /\ phase' = "appReadback"
  /\ resumeCalls' = [resumeCalls EXCEPT ![current] = @ + 1]
  /\ pendingEffect' = "resume"
  /\ appVisible' = IF effect THEN appVisible \union {current} ELSE appVisible
  /\ everAppVisible' = IF effect THEN everAppVisible \union {current}
                                     ELSE everAppVisible
  /\ UNCHANGED << current, completed, stoppedAt, filePresent, projectBound,
                  everFilePresent, everProjectBound, fileCalls, bindCalls,
                  mutationWhilePending, staging >>

ReadApp ==
  /\ phase = "appReadback"
  /\ pendingEffect = "resume"
  /\ phase' = IF current \in appVisible THEN "bindCall" ELSE "stopped"
  /\ stoppedAt' = IF current \in appVisible THEN stoppedAt ELSE current
  /\ pendingEffect' = "none"
  /\ UNCHANGED << current, completed, filePresent, appVisible, projectBound,
                  everFilePresent, everAppVisible, everProjectBound, fileCalls,
                  resumeCalls, bindCalls, mutationWhilePending, staging >>

BindProject(effect) ==
  /\ phase = "bindCall"
  /\ pendingEffect = "none"
  /\ current \in appVisible
  /\ bindCalls[current] = 0
  /\ phase' = "projectReadback"
  /\ bindCalls' = [bindCalls EXCEPT ![current] = @ + 1]
  /\ pendingEffect' = "bind"
  /\ projectBound' = IF effect THEN projectBound \union {current}
                                    ELSE projectBound
  /\ everProjectBound' = IF effect THEN everProjectBound \union {current}
                                        ELSE everProjectBound
  /\ UNCHANGED << current, completed, stoppedAt, filePresent, appVisible,
                  everFilePresent, everAppVisible, fileCalls, resumeCalls,
                  mutationWhilePending, staging >>

ReadProject ==
  /\ phase = "projectReadback"
  /\ pendingEffect = "bind"
  /\ phase' = IF current \notin projectBound
                 THEN "stopped"
                 ELSE IF current = 3 THEN "done" ELSE "fileCall"
  /\ current' = IF current \in projectBound /\ current < 3
                   THEN current + 1
                   ELSE current
  /\ completed' = IF current \in projectBound
                     THEN completed \union {current}
                     ELSE completed
  /\ stoppedAt' = IF current \in projectBound THEN stoppedAt ELSE current
  /\ pendingEffect' = "none"
  /\ UNCHANGED << filePresent, appVisible, projectBound, everFilePresent,
                  everAppVisible, everProjectBound, fileCalls, resumeCalls,
                  bindCalls, mutationWhilePending, staging >>

RewriteFileFault ==
  /\ Fault = "rewriteFile"
  /\ phase = "fileReadback"
  /\ pendingEffect = "file"
  /\ fileCalls[current] = 1
  /\ fileCalls' = [fileCalls EXCEPT ![current] = @ + 1]
  /\ mutationWhilePending' = TRUE
  /\ UNCHANGED << phase, current, completed, stoppedAt, filePresent,
                  appVisible, projectBound, everFilePresent, everAppVisible,
                  everProjectBound, resumeCalls, bindCalls, pendingEffect,
                  staging >>

RepeatResumeFault ==
  /\ Fault = "repeatResume"
  /\ phase = "appReadback"
  /\ pendingEffect = "resume"
  /\ resumeCalls[current] = 1
  /\ resumeCalls' = [resumeCalls EXCEPT ![current] = @ + 1]
  /\ mutationWhilePending' = TRUE
  /\ UNCHANGED << phase, current, completed, stoppedAt, filePresent,
                  appVisible, projectBound, everFilePresent, everAppVisible,
                  everProjectBound, fileCalls, bindCalls, pendingEffect,
                  staging >>

RepeatBindFault ==
  /\ Fault = "repeatBind"
  /\ phase = "projectReadback"
  /\ pendingEffect = "bind"
  /\ bindCalls[current] = 1
  /\ bindCalls' = [bindCalls EXCEPT ![current] = @ + 1]
  /\ mutationWhilePending' = TRUE
  /\ UNCHANGED << phase, current, completed, stoppedAt, filePresent,
                  appVisible, projectBound, everFilePresent, everAppVisible,
                  everProjectBound, fileCalls, resumeCalls, pendingEffect,
                  staging >>

OutOfOrderFault ==
  /\ Fault = "outOfOrder"
  /\ phase = "fileCall"
  /\ current = 1
  /\ current' = 2
  /\ phase' = "fileReadback"
  /\ fileCalls' = [fileCalls EXCEPT ![2] = @ + 1]
  /\ pendingEffect' = "file"
  /\ filePresent' = filePresent \union {2}
  /\ everFilePresent' = everFilePresent \union {2}
  /\ UNCHANGED << completed, stoppedAt, appVisible, projectBound,
                  everAppVisible, everProjectBound, resumeCalls, bindCalls,
                  mutationWhilePending, staging >>

ContinueAfterFailureFault ==
  /\ Fault = "continueAfterFailure"
  /\ phase = "stopped"
  /\ stoppedAt < 3
  /\ phase' = "fileCall"
  /\ current' = stoppedAt + 1
  /\ UNCHANGED << completed, stoppedAt, filePresent, appVisible, projectBound,
                  everFilePresent, everAppVisible, everProjectBound, fileCalls,
                  resumeCalls, bindCalls, pendingEffect, mutationWhilePending,
                  staging >>

RollbackFault ==
  /\ Fault = "rollback"
  /\ phase \in {"stopped", "done"}
  /\ everFilePresent # {}
  /\ \E p \in everFilePresent:
       /\ filePresent' = filePresent \ {p}
       /\ UNCHANGED << phase, current, completed, stoppedAt, appVisible,
                       projectBound, everFilePresent, everAppVisible,
                       everProjectBound, fileCalls, resumeCalls, bindCalls,
                       pendingEffect, mutationWhilePending, staging >>

DeleteStagingFault ==
  /\ Fault = "deleteStaging"
  /\ staging # {}
  /\ \E p \in staging:
       /\ staging' = staging \ {p}
       /\ UNCHANGED << phase, current, completed, stoppedAt, filePresent,
                       appVisible, projectBound, everFilePresent,
                       everAppVisible, everProjectBound, fileCalls,
                       resumeCalls, bindCalls, pendingEffect,
                       mutationWhilePending >>

Terminal == phase \in {"done", "stopped"}

TerminalStutter ==
  /\ Terminal
  /\ UNCHANGED vars

Next ==
  \/ \E effect \in BOOLEAN: InstallFile(effect)
  \/ ReadFile
  \/ \E effect \in BOOLEAN: ResumeApp(effect)
  \/ ReadApp
  \/ \E effect \in BOOLEAN: BindProject(effect)
  \/ ReadProject
  \/ RewriteFileFault
  \/ RepeatResumeFault
  \/ RepeatBindFault
  \/ OutOfOrderFault
  \/ ContinueAfterFailureFault
  \/ RollbackFault
  \/ DeleteStagingFault
  \/ TerminalStutter

TypeOK ==
  /\ phase \in {"fileCall", "fileReadback", "resumeCall", "appReadback",
                  "bindCall", "projectReadback", "done", "stopped"}
  /\ current \in Parts
  /\ completed \subseteq Parts
  /\ stoppedAt \in 0..3
  /\ filePresent \subseteq Parts
  /\ appVisible \subseteq Parts
  /\ projectBound \subseteq Parts
  /\ everFilePresent \subseteq Parts
  /\ everAppVisible \subseteq Parts
  /\ everProjectBound \subseteq Parts
  /\ fileCalls \in [Parts -> 0..2]
  /\ resumeCalls \in [Parts -> 0..2]
  /\ bindCalls \in [Parts -> 0..2]
  /\ pendingEffect \in {"none", "file", "resume", "bind"}
  /\ mutationWhilePending \in BOOLEAN
  /\ staging \subseteq Parts

CompletedInManifestOrder ==
  /\ (phase = "done" => completed = Parts)
  /\ (phase # "done" => completed = {p \in Parts: p < current})
  /\ \A p \in Parts:
       (fileCalls[p] + resumeCalls[p] + bindCalls[p] > 0) =>
         \A q \in Parts: q < p => q \in completed

EffectsFollowReadback ==
  \A p \in Parts:
    /\ (resumeCalls[p] > 0 => p \in filePresent /\ fileCalls[p] = 1)
    /\ (bindCalls[p] > 0 => p \in appVisible /\ resumeCalls[p] = 1)
    /\ (p \in completed => p \in projectBound /\ bindCalls[p] = 1)

EffectsAtMostOncePerInvocation ==
  \A p \in Parts:
    /\ fileCalls[p] <= 1
    /\ resumeCalls[p] <= 1
    /\ bindCalls[p] <= 1

UncertainEffectsUseReadbackOnly ==
  /\ ~mutationWhilePending
  /\ (phase = "fileReadback" => pendingEffect = "file")
  /\ (phase = "appReadback" => pendingEffect = "resume")
  /\ (phase = "projectReadback" => pendingEffect = "bind")
  /\ (pendingEffect = "none" =>
        phase \notin {"fileReadback", "appReadback", "projectReadback"})
  /\ (pendingEffect = "file" => phase = "fileReadback")
  /\ (pendingEffect = "resume" => phase = "appReadback")
  /\ (pendingEffect = "bind" => phase = "projectReadback")

StopOnFirstFailure ==
  stoppedAt = 0 \/
    /\ phase = "stopped"
    /\ current = stoppedAt
    /\ \A p \in Parts:
         p > stoppedAt =>
           /\ fileCalls[p] = 0
           /\ resumeCalls[p] = 0
           /\ bindCalls[p] = 0
           /\ p \notin completed

EffectsAreNotRolledBack ==
  /\ everFilePresent \subseteq filePresent
  /\ everAppVisible \subseteq appVisible
  /\ everProjectBound \subseteq projectBound

StagingIsPreserved == staging = Parts

EventuallyReported == <>Terminal

\* Liveness is conditional on the local coordinator continuing to schedule
\* enabled steps. The model does not prove that transport or App calls return.
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

=============================================================================
