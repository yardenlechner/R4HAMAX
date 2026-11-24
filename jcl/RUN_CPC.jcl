//R4HACPC JOB (ACCT),'CPC RAW R4HA',CLASS=A,MSGCLASS=X,
//             NOTIFY=&SYSUID
//* Raw hourly LAC diagnostics; not an SCRT/N5 billing calculation.
//* Customize job, source, date, input and CPCMAP inventory.
//* Names below are fictional placeholders, not a site configuration.
//* Add unnamed SMFIN DD statements for additional input files.
//* See docs/CPC_MODE.md before submitting.
//* Keep actual site data out of git.
//RUN      EXEC PGM=IKJEFT1B,REGION=64M,DYNAMNBR=20
//SYSEXEC  DD DISP=SHR,DSN=YOURHLQ.REXX
//SMFIN    DD DISP=SHR,DSN=YOURHLQ.SMF.DUMP
//CPCMAP   DD DISP=SHR,DSN=YOURHLQ.R4HA.CPCMAP
//REPORT   DD SYSOUT=*,DCB=(RECFM=VB,LRECL=260,BLKSIZE=0)
//CSVOUT   DD SYSOUT=*,DCB=(RECFM=VB,LRECL=260,BLKSIZE=0)
//SYSTSPRT DD SYSOUT=*
//SYSTSIN  DD *
 %R4HAMAX CPC=Y DATE=2026251 SID=* HOURLY=Y CSV=Y
/*
