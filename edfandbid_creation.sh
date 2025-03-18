#!/bin/bash
## By Julia Dengler 

## INPUT FOLDER IS THE FOLDER WITH THE MEF FILES, REQUIRED: FOLDER NAME IS SUBJECT ID (ex. HUP199_phaseII)
## MODULE FOLDER IS THE FOLDER WITH THE REQUIRED SCRIPTS AND PACKAGES

############ Print out what the user inputted for input and module folders ###############################
echo "Input Folder: $1"
echo "Module Folder: $2"
echo "Type (scalp or ieeg): $3"

############ Set the input and module folders based on user input ########################################
inputfolder="$1"
modulefolder="$2"
type="$3"


############  Run jar file that converts mef to edf ######################################################
java -jar ${modulefolder}/mefstreamer.jar ${inputfolder}


############  Unzip any folders within the input folder ##################################################
# Debugging: List the zip files found in the input folder
echo "Looking for zip files in $inputfolder"

find "$inputfolder" -type f -name "*.zip" -print
find "$inputfolder" -type f -name "*.zip" | while IFS= read -r file; do
  echo "Unzipping: $file"
  
  # Unzip each zip file into its own directory
  unzip -o -q "$file" -d "$(dirname "$file")" && echo "Successfully unzipped: $file" || echo "Failed to unzip: $file"

done

find "$inputfolder" -type d -name "*MACOSX*" -print0 | xargs -0 rm -rf

########### If imaging folder exists, unzip any files ####################################################
imagingfolder=$(find "$inputfolder" -type d -iname "*imag*")
echo "Imaging folder found: $imagingfolder"  # Debugging line
if [ -z "$imagingfolder" ]; then
   echo "No imaging folder found"
else
  cd "$imagingfolder"
  for file in *.nii.gz; do
     gunzip "$file"
  done
  cd ..
  rm -f ${imagingfolder}.zip
fi

########### Run python script that puts everything into BIDs #############################################
# Install dependencies
pip install --no-cache-dir -r requirements.txt

python "${modulefolder}/postbids.py" "$inputfolder" "$modulefolder" "$type"

############ Move reconstruction directory ###############################################################
# Find if reconstruction folder exists and move into Derivative Directory
reconstring="recon"
recon_folder=$(find ${inputfolder} -type d -iname "*$reconstring*")

if [ -z "$recon_folder" ]; then
  echo "No reconstruction folder found"
else
  mv "$recon_folder" ${inputfolder}/Derivative
  rm -f ${recon_folder}.zip
fi

############# Remove mef files, other folders, and xml files, and move everything else to Derivative ####
rm -f ${inputfolder}/*.mef
rm -f ${inputfolder}/*.xml
rm -r ${imagingfolder}

find ${inputfolder} -maxdepth 1 -type f -exec mv {} ${inputfolder}/Derivative \;
echo "Finished edf conversion and bids creation"
