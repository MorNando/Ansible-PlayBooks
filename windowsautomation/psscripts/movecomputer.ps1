$targetOU = ""
$VMName = ''

Function Move-VMtoAnotherOU {
    param(
        [string]$VMName,
        [string]$TargetOU
    )
    Import-Module ActiveDirectory
    get-adcomputer $VMName | Move-ADObject -TargetPath $TargetOU
}

Move-VMtoAnotherOU -VMName $VMName -TargetOU $targetOU
