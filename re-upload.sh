for i in {37..127}; do
     pennsieve upload manifest "$i" >> upload.log 2>&1
done

