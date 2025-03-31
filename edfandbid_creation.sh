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
objectstr="/objects/"
objectsfolder="${inputfolder}${objectstr}"

############  Run jar file that converts mef to edf ######################################################
#java -jar ${modulefolder}/mefstreamer.jar ${inputfolder}


############ Delete reconstruction directory ###############################################################
reconstring="recon"
find "$objectsfolder" -type f -iname "*$reconstring*.zip" -print |
while IFS= read -r zipfile; do
  echo "Found zip file: $zipfile"
  
  # Delete the file
  rm "$zipfile" && echo "Deleted: $zipfile" || echo "Failed to delete: $zipfile"
done

############### Remove mef and any other files ###########################################
#rm -f ${inputfolder}/*.mef
rm -f ${inputfolder}/*.xml

############  Unzip any folders within the input folder ##################################################
# Debugging: List the zip files found in the input folder
imagstring="/imaging/"
mkdir ${objectsfolder}/imaging
echo "Looking for zip files in $objectsfolder"

find "$objectsfolder" -type f -name "*.zip" -print
find "$objectsfolder" -type f -name "*.zip" | while IFS= read -r file; do
  echo "Unzipping: $file"
  
  # Unzip each zip file into its own directory
  #unzip -o -q "$file" -d "$(dirname "$file")" && echo "Successfully unzipped: $file" || echo "Failed to unzip: $file"
  unzip -o -q "$file" -d "$(dirname "$file")/$imagstring" && echo "Successfully unzipped: $file" || echo "Failed to unzip: $file"

done

find "$objectsfolder" -type d -name "*MACOSX*" -print0 | xargs -0 rm -rf

########### If imaging folder exists, unzip any files ####################################################
imagingfolder=$(find "$objectsfolder" -type d -iname "*imag*")
echo "Imaging folder found: $imagingfolder"  # Debugging line
if [ -z "$imagingfolder" ]; then
   echo "No imaging folder found"
else
  cd "$imagingfolder"
  find . -mindepth 2 -type f -exec mv {} "${objectsfolder}/imaging/" \;
  for file in *.nii.gz; do
     gunzip "$file"
  done
  cd ..
  rm -f ${imagingfolder}.zip
fi

########### Run python script that puts everything into BIDs #############################################
# Install dependencies
pip3 install --no-cache-dir -r /home/ec2-user/migrationtools/requirements.txt
new_path=$(python3 "${modulefolder}/postbids.py" "$inputfolder" "$modulefolder" "$type" | xargs)
  
echo "$new_path"
############# Remove object folder and move everything else to derivative  ####
#rm -r ${new_path}/objects

#find ${new_path} -maxdepth 1 -type f -exec mv {} ${new_path}/Derivative \;

echo "Finished edf conversion and bids creation"