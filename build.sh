#!/bin/bash
# Create a Python package to deploy to AWS Lambda.

installed () {
  command -v "$1" >/dev/null 2>&1
}

githead () {
  cd $1
  git rev-parse HEAD >/dev/null 2>&1
}

package() {
  echo "Creating package..."
  cd $2 && zip -qr $1 * && cd -
}

package-add() {
  echo "Adding build files to package..."
  cd $2 && zip -qr --grow $1 * && cd -
}

[ $# != 1 ] && {
  echo "usage: $0 <path-to-package>"
  exit 1
}

TARGET_DIR=$(realpath $1)
CURRENT_DIR=$PWD

for cmd in pip2 zip git; do
  ! installed $cmd && {
    echo "error: $cmd not found"
    exit 1
  }
done

if [ -z "$(githead $TARGET_DIR)" ]; then
  PACKAGE_NAME="${TARGET_DIR}-latest.zip"
else
  PACKAGE_NAME="${TARGET_DIR}-$(githead $TARGET_DIR).zip"
fi

if [ -f ${PACKAGE_NAME} ]; then
  echo "$(basename ${PACKAGE_NAME}) exists in the current directory"
  read -p "overwrite?(y/n)" confirm
  [ "$confirm" != "y" ] && {
    echo "aborted"
    exit 1
  }
  rm -f ${PACKAGE_NAME}
fi

package $PACKAGE_NAME $TARGET_DIR

if [ -f "${TARGET_DIR}/requirements.txt" ]; then 
  echo "Packaging pip requirements..."
  TMPDIR=$(mktemp -d /tmp/lambdapack.XXXX)
  pip2 install -r ${TARGET_DIR}/requirements.txt -t $TMPDIR 1>> ${TMPDIR}/.buildlog
  package-add $PACKAGE_NAME $TMPDIR
fi

echo "done"
exit 0
